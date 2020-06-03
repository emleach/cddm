"""
Demonstrates how to compute fft of videos and the compute auto correlation
function with the out-of-memory version of the multitau algorithm.
"""
from cddm.viewer import DataViewer
from cddm.video import multiply, normalize_video, crop, asarrays
from cddm.window import blackman
from cddm.fft import rfft2, normalize_fft
from cddm.core import acorr, normalize, stats
from cddm.multitau import log_average
from cddm.sim import seed

import numpy as np

#: see video_simulator for details, loads sample video
import examples.paper.standard_video as video_simulator
import importlib

seed(0)
importlib.reload(video_simulator) #recreates iterator

from examples.paper.conf import KIMAX, KJMAX, SHAPE, NFRAMES_STANDARD, DATA_PATH, PERIOD, NFRAMES_RANDOM


#: create window for multiplication...
window = blackman(SHAPE)

#: we must create a video of windows for multiplication
window_video = ((window,),)*NFRAMES_STANDARD

#:perform the actual multiplication
video = multiply(video_simulator.video, window_video)

#: if the intesity of light source flickers you can normalize each frame to the intensity of the frame
#video = normalize_video(video)

#: perform rfft2 and crop results, to take only first kimax and first kjmax wavenumbers.
fft = rfft2(video, kimax = KIMAX, kjmax = KJMAX)

#: you can also normalize each frame with respect to the [0,0] component of the fft
#: this it therefore equivalent to  normalize_video
#fft = normalize_fft(fft)

#load in numpy array
fft_array, = asarrays(fft, NFRAMES_STANDARD)

if __name__ == "__main__":
    import os.path as p

    #: now perform auto correlation calculation with default parameters 
    data = acorr(fft_array,n =NFRAMES_RANDOM//PERIOD*2, method = "fft")
    bg, var = stats(fft_array)
    
    #: perform normalization and merge data
    data_lin = normalize(data, bg, var, scale = True)
    
    #: inspect the data
    viewer = DataViewer()
    viewer.set_data(data_lin)
    viewer.set_mask(k = 25, angle = 0, sector = 30)
    viewer.plot()
    viewer.show()
    
    #: perform log averaging
    x,y = log_average(data_lin, size = 16)
    
    #: save the normalized data to numpy files
    np.save(p.join(DATA_PATH, "corr_standard_t.npy"),x*PERIOD/2.)
    np.save(p.join(DATA_PATH, "corr_standard_data.npy"),y)


