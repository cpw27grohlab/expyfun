"""Stimulus generation functions
"""

import numpy as np

from ..io import read_hdf5
from ._filter import resample
from .._utils import fetch_data_file, _fix_audio_dims


# This was used to generate "barb_anech.gz":
#
# from scipy import io as spio
# mat = spio.loadmat('anechRev.mat')
# x = np.concatenate([mat[key][:, 0, -1, :].T.astype(np.float64)[:, None, :]
#                     for key in ['fimp_l', 'fimp_r']], axis=1)
# keep = np.abs(x) > np.max(np.abs(x)) * 1e-5
# idx = int(2 ** np.ceil(np.log2(np.where(np.any(np.any(keep, 1), 0))[0][-1])))
# x = x[:, :, :idx]
# sig = np.random.RandomState(0).randn(100000)
# res = np.array([np.convolve(sig, xx) for xx in x[0]])[:, idx:-idx]
# x /= np.mean(np.sqrt(np.mean(res ** 2, axis=1)))
# with gzip.open('barb_brir.gz', 'w') as fid:
#     fid.write(x.tostring())
# angles = np.arange(0, 91, 15, dtype=float)
# with gzip.open('barb_angles.gz', 'w') as fid:
#     fid.write(angles.tostring())
#
# Then the files were uploaded to lester.


def _get_hrtf(angle, source, fs):
    """Helper to sub-select proper BRIR

    HRTF files must be .hdf5 files written by ``write_hdf5``. The dict stored
    in that file must contain the following: ``brir``: the BRIR data with shape
    (n_angles, 2, n_time_points); ``angles``: the angles (all within [0, 180])
    of the BRIRs; ``fs``: the sampling rate.

    The amplitude should be normalized such that the sum of squares of the
    0-degree BRIRs (mean of that across channels) is equal to 1. This will
    ensure that the RMS of a white signal filtered with this signal is
    unchanged.
    """
    fname = '{0}_{1}.hdf5'.format(source, fs)
    fname = fetch_data_file('hrtf/{0}'.format(fname))
    data = read_hdf5(fname)
    angles = data['angles']
    leftward = False
    read_angle = angle
    if angle < 0:
        leftward = True
        read_angle = -angle
    if read_angle not in angles:
        raise ValueError('angle "{0}" must be one of +/-{1}'
                         ''.format(angle, list(angles)))
    brir = data['brir']
    idx = np.where(angles == read_angle)[0]
    assert len(idx) == 1
    brir = brir[idx[0]].copy()
    return brir, data['fs'], leftward


def convolve_hrtf(data, fs, angle, source='barb'):
    """Convolve a signal with a head-related transfer function

    Technically we will be convolving with binaural room impluse
    responses (BRIRs), but HRTFs (freq-domain equiv. representations)
    are the common terminology.

    Parameters
    ----------
    data : 1-dimensional or 1xN array-like
        Data to operate on.
    fs : float
        The sample rate of the data. (HRTFs will be resampled if necessary.)
    angle : float
        The azimuthal angle of the HRTF.
    source : str
        Source to use for HRTFs. Currently `'barb'` and `'cipic'` are
        supported.

    Returns
    -------
    data_hrtf : array
        A 2D array ``shape=(2, n_samples)`` containing the convolved data.

    Notes
    -----
    CIPIC data downloaded from:

        http://earlab.bu.edu/databases/collections/cipic/Default.aspx.

    Additional documentation:

        http://earlab.bu.edu/databases/collections/cipic/documentation/hrir_data_documentation.pdf  # noqa

    The data were modified to suit our experimental needs. Below is the
    liceneing information for the CIPIC data:

    **Copyright**

    Copyright (c) 2001 The Regents of the University of California. All Rights
    Reserved.

    **Disclaimer**

    THE REGENTS OF THE UNIVERSITY OF CALIFORNIA MAKE NO REPRESENTATION OR
    WARRANTIES WITH RESPECT TO THE CONTENTS HEREOF AND SPECIFICALLY DISCLAIM
    ANY IMPLIED WARRANTIES OR MERCHANTABILITY OR FITNESS FOR ANY PARTICULAR
    PURPOSE.

    Further, the Regents of the University of California reserve the right to
    revise this software and/or documentation and to make changes from time to
    time in the content hereof without obligation of the Regents of the
    University of California to notify any person of such revision or change.

    Use of Materials
    The Regents of the University of California hereby grant users permission
    to reproduce and/or use materials available therein for any purpose-
    educational, research or commercial. However, each reproduction of any part
    of the materials must include the copyright notice, if it is present.

    In addition, as a courtesy, if these materials are used in published
    research, this use should be acknowledged in the publication. If these
    materials are used in the development of commercial products, the Regents
    of the University of California request that written acknowledgment of such
    use be sent to:

    CIPIC- Center for Image Processing and Integrated Computing University of
    California 1 Shields Avenue Davis, CA 95616-8553
    """
    fs = float(fs)
    angle = float(angle)
    known_sources = ['barb', 'cipic']
    known_fs = [24414, 44100]  # must be sorted
    if source not in known_sources:
        raise ValueError('Source "{0}" unknown, must be one of {1}'
                         ''.format(source, known_sources))
    data = np.array(data, np.float64)
    data = _fix_audio_dims(data, n_channels=1).ravel()

    # Find out which sampling rate to get--first that is >= fs
    # Use the last, highest one whether it is high enough or not
    ge = [int(np.round(fs)) <= k for k in known_fs[:-1]] + [True]
    brir_fs = known_fs[ge.index(True)]

    brir, brir_fs, leftward = _get_hrtf(angle, source, brir_fs)
    order = [1, 0] if leftward else [0, 1]
    if not np.allclose(brir_fs, fs, rtol=0, atol=0.5):
        brir = [resample(b, fs, brir_fs) for b in brir]
    out = np.array([np.convolve(data, brir[o]) for o in order])
    return out
