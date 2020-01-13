from typing import List, Optional, Any
import sys
from i18n import t
import wave
from pathlib import Path
import struct
import numpy
from matplotlib import pyplot as plt
import const
import mido

def interpolation(list: List, position: float) -> Optional[Any]:
    int_position = int(position)
    try:
        return list[int_position] * (int_position + 1 - position)\
             + list[int_position + 1] * (position - int_position)
    except IndexError:
        return None

def click_to_continue():
    input(t("console.click_to_continue"))

def getWavefile(path: Path, mode="r"):
    abspath: Path = path.absolute()
    if not abspath.exists():
        raise ValueError("file does not exist")
    if not abspath.is_file:
        raise TypeError("Only accept paths to one file")
    return wave.open(abspath, mode)

def setupChannels(wavefile, channel=None):
    num_frames = wavefile.getnframes()
    sample_width = wavefile.getsampwidth()
    if sample_width not in [2, 4]:
        raise ValueError("Unsupported Wave File (Sample Width).")
    else:
        packtype = {
            2: "h", 4: "l"
        }[sample_width]
    result = numpy.zeros(num_frames)
    for i in range(num_frames * 4):
        if i % 4 == 0:
            offset = i // 4
            value = wavefile.readframes(1)
            if not channel:
                left = value[0: sample_width]
                right = value[sample_width: 2 * sample_width]
                result[offset] = \
                    round(struct.unpack(packtype, left)[0] +
                        struct.unpack(packtype, right)[0]
                    ) / 2
    return result

def load_specgram(framerate, channels, NFFT=2400, NT=5):
    try:
        return plt.specgram(channels, 
            NFFT=NFFT, Fs=framerate, 
            noverlap=NFFT-(float(framerate)/960*NT)
        )
    except MemoryError:
        return None

def gen_mapping(specgram, limvel=1, NFFT=2400):
    result = []
    for i in range(len(specgram[0][0])):
        imi = []
        n0i = []

        for k in range(len(specgram[0])):
            n0i.append(specgram[0][k][i])

        for j in range(128):
            imi.append(
                numpy.sqrt(numpy.sqrt(
                    interpolation(n0i, const.pitch[j] / Fs * NFFT)
                )) * 4 / limvel)
        result.append(imi)
    
def gen_midifile(mapping_list, type=1):
    midi = mido.MidiFile(type=type)
    for _ in range(8):
        midi.add_track()
    first_row = [0] * 8
    tc = [0] * 8
    num_i = len(mapping_list)
    list_old = [midi.tracks[i] for i in range(8)]
    