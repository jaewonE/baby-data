import torch.nn as nn
import torchaudio
import torch


class AugmentMelSTFT(nn.Module):
    def __init__(self, n_mels=128, sr=32000, win_length=800, hopsize=320, n_fft=1024, freqm=48, timem=192,
                 fmin=0.0, fmax=None, fmin_aug_range=10, fmax_aug_range=2000):
        torch.nn.Module.__init__(self)

        self.win_length = win_length
        self.n_mels = n_mels
        self.n_fft = n_fft
        self.sr = sr
        self.fmin = fmin
        if fmax is None:
            fmax = sr // 2 - fmax_aug_range // 2
            print(f"Warning: FMAX is None setting to {fmax} ")
        self.fmax = fmax
        self.hopsize = hopsize
        self.register_buffer('window',
                             torch.hann_window(win_length, periodic=False),
                             persistent=False)
        assert fmin_aug_range >= 1, f"fmin_aug_range={fmin_aug_range} should be >=1; 1 means no augmentation"
        assert fmax_aug_range >= 1, f"fmax_aug_range={fmax_aug_range} should be >=1; 1 means no augmentation"
        self.fmin_aug_range = fmin_aug_range
        self.fmax_aug_range = fmax_aug_range

        self.register_buffer("preemphasis_coefficient",
                             torch.as_tensor([[[-.97, 1]]]), persistent=False)
        if freqm == 0:
            self.freqm = torch.nn.Identity()
        else:
            self.freqm = torchaudio.transforms.FrequencyMasking(
                freqm, iid_masks=True)
        if timem == 0:
            self.timem = torch.nn.Identity()
        else:
            self.timem = torchaudio.transforms.TimeMasking(
                timem, iid_masks=True)

    def forward(self, x):
        x = nn.functional.conv1d(x.unsqueeze(
            1), self.preemphasis_coefficient).squeeze(1)
        x = torch.stft(x, self.n_fft, hop_length=self.hopsize, win_length=self.win_length,
                       center=True, normalized=False, window=self.window, return_complex=False)
        x = (x ** 2).sum(dim=-1)  # power mag
        fmin = self.fmin + torch.randint(self.fmin_aug_range, (1,)).item()
        fmax = self.fmax + self.fmax_aug_range // 2 - \
            torch.randint(self.fmax_aug_range, (1,)).item()
        # don't augment eval data
        if not self.training:
            fmin = self.fmin
            fmax = self.fmax

        mel_basis, _ = torchaudio.compliance.kaldi.get_mel_banks(self.n_mels,  self.n_fft, self.sr,
                                                                 fmin, fmax, vtln_low=100.0, vtln_high=-500., vtln_warp_factor=1.0)
        mel_basis = torch.as_tensor(torch.nn.functional.pad(mel_basis, (0, 1), mode='constant', value=0),
                                    device=x.device)
        with torch.cuda.amp.autocast(enabled=False):
            melspec = torch.matmul(mel_basis, x)

        melspec = (melspec + 0.00001).log()

        if self.training:
            melspec = self.freqm(melspec)
            melspec = self.timem(melspec)

        melspec = (melspec + 4.5) / 5.  # fast normalization

        return melspec


def get_augmentMelSTFT(audio_file: str, to_numpy: bool = False) -> torch.Size:
    # waveform = librosa.core.load(audio_file,sr=32000, mono=True)[0]  # numpy.ndarray: (288000,)
    waveform = torchaudio.load(audio_file)[0]  # torch.Size([1, 288000])

    spec = mel(waveform)  # torch.Size([1, 128, 1800])

    # unsqueezed_spec = spec.unsqueeze(0)  # torch.Size([1, 1, 128, 1800])
    return spec.numpy() if to_numpy else spec


if __name__ == '__main__':
    # mel = AugmentMelSTFT(n_mels=128, sr=16000, win_length=800, hopsize=320)
    mel = AugmentMelSTFT(
        n_mels=128,
        sr=16000,
        win_length=400,
        hopsize=160,
        n_fft=800
    )

    file_list = ["/Users/jaewone/Downloads/무제 폴더/new_test.wav"]
    for file in file_list:
        mel_spectogram = get_augmentMelSTFT(file, to_numpy=True)
        print(type(mel_spectogram))
        print(mel_spectogram.shape)
