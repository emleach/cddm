"""
Data mapping and k-averaging functions.
"""

import numpy as np

#from cddm.conf import F64,I64,U16, U16DTYPE, F, I, FDTYPE, I64DTYPE,F64DTYPE, NUMBA_CACHE

#@numba.jit([I64[:,:](I64,I64,F64)],nopython = True, cache = NUMBA_CACHE)
#def line_indexmap(height, width, angle):
#    shape = (height,width)
#    s = np.empty(shape, I64DTYPE)
#    s[...] = -1
#    y,x = (s.shape[0]//2+1),s.shape[1]
#
#    angle = angle * np.pi/180
#    absangle = abs(angle)
#    
#    if absangle <= math.atan2(y,x) and absangle >=0:
#        for j in range(x):
#            i = - int(round(math.tan(angle)*j))
#            s[i,j] = j 
#    elif absangle > math.atan2(y,x) and absangle <= 90:
#        if angle > 0:
#            angle = np.pi/2 - angle 
#            for r,i in enumerate(range(y)):
#                j = int(round(math.tan(angle)*i))
#                s[-i,j] = r
#        else:
#            angle = angle+ np.pi/2
#            for r,i in enumerate(range(y)):
#                j =  int(round(math.tan(angle)*i))
#                s[i,j] = r            
#    return s         

 
def sector_indexmap(kmap, anglemap, angle = 0., sector = 30., kstep = 1.):
    """Builds indexmap array of integers ranging from -1 (invalid data)
    and positive integers. Each non-negative integer is a valid k-index computed
    from sector parameters.
    
    Parameters
    ----------
    kmap : ndarray
        Size of wavevector at each (i,j) indices in the rfft2 ouptut data.
    anglemap : ndarray
        Angle of the wavevector at each (i,j) indices in the rfft2 ouptut data.      
    angle : float
        Mean angle of the sector in degrees (-90 to 90).
    sector : float
        Width of the sector in degrees (between 0 and 180) 
    kstep : float, optional
        k resolution in units of minimum step size.
        
    Returns
    -------
    map : ndarray
        Ouput array of non-zero valued k-indices where data is valid, -1 elsewhere.
    """
    if angle < -90 or angle > 90:
        raise ValueError("Wrong angle value")
    if sector <= 0 or sector > 180:
        raise ValueError("Wrong sector value")
    kmax = kmap.max()
    ks = np.arange(0, kmax + kstep, kstep)
    
    out = np.empty(kmap.shape, int)
    out[...] =-1
    
    high = np.pi/180*(angle + sector/2)
    low  = np.pi/180*(angle - sector/2)
    
    m = np.pi/2
    negate = False
        
    if high > m:
        low, high = high%(-m), low
        negate = True
    elif low < -m:
        high, low = low%m, high
        negate = True
        
    if negate:
        fmask = (anglemap <= high) & (anglemap > low)
        fmask = np.logical_not(fmask)
    else:
        fmask = (anglemap < high) & (anglemap >= low)
    
    for i,k in enumerate(ks):
        kmask = (kmap <= (k + kstep/2.)) &  (kmap > (k - kstep/2.))
        mask = kmask & fmask
        out[mask] = i
    half = kmap.shape[0]//2+1
    #no new information here... so remove it
    out[half:,0] = -1
    #k = (0,0) is present regardless of angle, sector
    out[0,0] = 0
    return out


def _get_steps_size(kisize,kjsize,shape):
    height, width = (1, 1) if shape is None else shape
    
    if kjsize is None:
        if shape is None:
            raise ValueError("Shape is a required argument")
        kjsize = width//2+1

    if kisize is None:
        if shape is None:
            raise ValueError("Shape is a required argument")
        kisize = height
    
    kistep = 1.
    kjstep = 1.
    
    if height > width:
        kjstep = height/width
    else:
        kistep = width/height
    return (kisize, kistep), (kjsize, kjstep)

def rfft2_kangle(kisize = None, kjsize = None, shape = None):
    """Build k,angle arrays based on the size of the fft. 
    
    Parameters
    ----------
    kisize : int
        i-size of the cropped rfft2 data. 
    kjsize : int
        j-size of the cropped rfft2 data
    shape : (int,int)
        Shape of the original data. This is used to calculate step size. If not
        given, rectangular data is assumed (equal steps).
    """
    (kisize, kistep), (kjsize, kjstep) = _get_steps_size(kisize,kjsize,shape)
            
    y,x = np.meshgrid(np.fft.fftfreq(kisize)*kisize*kistep,np.arange(kjsize)*kjstep, indexing = "ij")  
    x2, y2  = x**2, y**2
    return (x2 + y2)**0.5 , np.arctan2(-y,x)  

def _k_select(data, k, indexmap, kmap):
    mask = (indexmap == int(round(k)))
    ks = kmap[mask]
    if len(ks) > 0:
        #at least one k value exists
        data_avg = data[...,mask,:].mean(-2)
        k_avg = ks.mean()
        return k_avg, data_avg  
    else:
        #no k values
        return None
    
class KMask(object):
    kmap = None
    anglemap = None
    def __init__(self, kisize, kjsize, shape = None):
        self.kmap, self.anglemap = rfft2_kangle(kisize, kjsize,shape)
    
    def get(self):
        pass


def k_select(data, angle , sector = 5, kstep = 1, k = None, shape = None):
    """k-selection and k-averaging of normalized (and merged) correlation data.
    
    This function takes (...,i,j,n) correlation data and performs k-based selection
    and averaging of the data.
    
    Parameters
    ----------
    deta : array_like
        Input correlation data of shape (...,i,j,n)
    angle : float
        Angle between the j axis and the direction of k-vector
    sector : float, optional
        Defines sector angle, k-data is avergaed between angle+sector and angle-sector angles
    kstep : float, optional
        Defines an approximate k step in pixel units
    k : float or list of floats, optional
        If provided, only return at a given k value (and not at all non-zero k values)
        
    Returns
    -------
    out : iterator, or tuple
        If k s not defined, this is an iterator that yields a tuple of (k_avg, data_avg)
        of actual (mean) k and averaged data. If k is a list of indices, it returns
        an iterator that yields a tuple of (k_avg, data_avg) for every non-zero data
        if k is an integer, it returns a tuple of (k_avg, data_avg) for a given k-index.
    """
    
    assert sector > 0
    
    kmap, anglemap = rfft2_kangle(data.shape[-3], data.shape[-2],shape)
    indexmap = sector_indexmap(kmap, anglemap, angle, sector, kstep)

    if k is None:
        kdim = indexmap.max() + 1
        k = np.arange(kdim)
    try:
        iterator = (_k_select(data, kk, indexmap, kmap) for kk in k)
        return tuple((data for data in iterator if data is not None))       
    except TypeError:
        #not iterable
        return _k_select(data, k, indexmap, kmap)
    

if __name__ == "__main__":
    import matplotlib.pyplot as plt
    k,f = rfft2_kangle(129,65, (256,256))
    m = sector_indexmap(k,f, angle = 0,sector = 30)
    plt.imshow(np.fft.fftshift(m,0))
    
    kmask = m == 32
    plt.figure()
    plt.imshow(np.fft.fftshift(kmask,0))
    