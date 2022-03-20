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
            value = wavefile.readframes(1)
            if not channel:
                left = value[:sample_width]
                right = value[sample_width: 2 * sample_width]
                offset = i // 4
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

def gen_mapping(specgram, framerate, limvel=1, NFFT=2400):
    result = []
    for i in range(len(specgram[0][0])):
        n0i = [specgram[0][k][i] for k in range(len(specgram[0]))]

        imi = [numpy.sqrt(numpy.sqrt(
                    interpolation(n0i, const.pitch[j] / framerate * NFFT)
                )) * 4 / limvel for j in range(128)]
        result.append(imi)
    return result
    
def gen_midifile(mapping_list, output_filename, type=1, lim=8, NT=5, BPM=500):
    notec = 0
    tempo = 500
    ratio = 2
    offlist = [[]] * 8

    tempo = mido.bpm2tempo(BPM)
    temp_int = int(NT * (tempo / 500.0) + 0.5)

    midi = mido.MidiFile(type=type)
    for _ in range(8):
        midi.add_track()
    first_row = [0] * 8
    tc = [0] * 8
    num_i = len(mapping_list)
    list_old = [midi.tracks[i] for i in range(8)]
    for column in range(num_i):
        for row in range(len(mapping_list[0])):
            vol = mapping_list[column][row]
            if vol <= lim:
                continue
            for l in range(8):
                if vol <= 32 + 32 * l and vol > 32 * l:
                    notec += 1
                    _v = int(vol / ratio + 0.5)
                    m1, m2 = 0, 0
                    if first_row[l]:
                        m1 = tc[l] - temp_int
                        m2 = temp_int
                        tc[l] = 0
                        first_row[l] = False
                    list_old[l].append(
                        mido.Message("note_on",
                            note=row,
                            time=m1,
                            velocity=_v if _v < 128 else 127
                        )
                    )
                    offlist[l].append(
                        mido.Message("note_off",
                            note=row,
                            time=m2,
                            velocity=_v if _v < 128 else 127
                        )
                    )
        for num in range(8):
            tc[num] += temp_int
            list_old[num].extend(offlist[num])
            offlist[num] = []
            first_row[num] = True

    for l in range(8):
        m1 = tc[l] - temp_int
        tc[l] = 0
        first_row[l] = False
        list_old[l].append(
            mido.Message('note_on',
                note=row,
                time=m1,
                velocity=1
            )
        )
        offlist[l].append(
            mido.Message('note_off',
                note=row,
                time=0,
                velocity=1
            )
        )

        list_old[l].extend(offlist[num])
        offlist[l] = []

    for i in list_old:
        i.append(mido.MetaMessage("end_of_track"))

    midi.save(output_filename)