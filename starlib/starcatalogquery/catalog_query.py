import os
import re
import numpy as np
import pandas as pd
from astropy.coordinates import SkyCoord

# 星表目录名(sc_name)可能与分块 CSV 前缀不一致（如 .../2mass_hmag/... 下文件为 2mass_xx-0.csv）
_TILE_FILE_PREFIX_CACHE = {}


def _catalog_tile_dir(sc_path: str) -> str:
    p = os.path.normpath(sc_path.replace("/", os.sep))
    return p if p.endswith(os.sep) else p + os.sep


def _resolve_tile_csv_prefix(sc_path: str, sc_name: str) -> str:
    """
    分块文件名为 ``{prefix}-{tile_index}.csv``。prefix 通常等于路径中的 sc_name，
    若不一致则从目录内已有 .csv 推断（取数量最多的前缀）。
    """
    key = (sc_path, sc_name)
    if key in _TILE_FILE_PREFIX_CACHE:
        return _TILE_FILE_PREFIX_CACHE[key]

    d = _catalog_tile_dir(sc_path)
    try:
        if not os.path.isdir(d.rstrip(os.sep)):
            _TILE_FILE_PREFIX_CACHE[key] = sc_name
            return sc_name
    except OSError:
        _TILE_FILE_PREFIX_CACHE[key] = sc_name
        return sc_name

    probe = d + sc_name + "-0.csv"
    if os.path.isfile(probe):
        _TILE_FILE_PREFIX_CACHE[key] = sc_name
        return sc_name

    tile_pat = re.compile(r"^(.+)-(\d+)\.csv$")
    prefix_counts = {}
    try:
        for name in os.listdir(d.rstrip(os.sep)):
            m = tile_pat.match(name)
            if m:
                pre = m.group(1)
                prefix_counts[pre] = prefix_counts.get(pre, 0) + 1
    except OSError:
        _TILE_FILE_PREFIX_CACHE[key] = sc_name
        return sc_name

    if sc_name in prefix_counts:
        _TILE_FILE_PREFIX_CACHE[key] = sc_name
        return sc_name
    if prefix_counts:
        best = max(prefix_counts, key=lambda k: prefix_counts[k])
        _TILE_FILE_PREFIX_CACHE[key] = best
        return best

    _TILE_FILE_PREFIX_CACHE[key] = sc_name
    return sc_name

def from_cap(theta,clat,clon,lmax):
    """
    Mask grid points using spherical cap.
    Reference: https://github.com/SHTOOLS/SHTOOLS/blob/master/pyshtools/shclasses/shgrid.py

    Usage:
        >>> mask_cap = from_cap(theta,clat,clon,lmax])
    Inputs:
        theta -> [float] The angular radius of the spherical cap in [deg]
        clat, clon -> [float] Latitude and longitude of the center of the spherical cap in [deg]
        lmax -> [int] The maximum spherical harmonic degree resolvable by the grid
    Outputs:
        mask_cap -> [numpy array] Grid points with spherical cap masked
    """
    step = 90/(lmax+1)
    lats = np.deg2rad(np.arange(90,-90,-step))
    lons = np.deg2rad(np.arange(0,360,step))
    nlat,nlon = len(lats),len(lons)
    array = np.zeros((nlat, nlon))

    theta = np.deg2rad(theta)
    clat = np.deg2rad(clat)
    clon = np.deg2rad(clon)

    # Set array equal to 1 within the cap
    imin = np.inf
    imax = 0
    for i, lat in enumerate(lats):
        if lat <= clat + theta:
            if i <= imin: imin = i
        if lat >= clat - theta:
            if i >= imax: imax = i

    x = np.cos(clat) * np.cos(clon)
    y = np.cos(clat) * np.sin(clon)
    z = np.sin(clat)

    coslon = np.cos(lons)
    sinlon = np.sin(lons)
    costheta = np.cos(theta)

    for i in range(imin, imax+1):
        coslat = np.cos(lats[i])
        sinlat = np.sin(lats[i])
        for j in range(0, nlon):
            dist = coslat * (x * coslon[j] + y * sinlon[j]) + z * sinlat
            if dist >= costheta: array[i, j] = 1
    return array

def seq2radec(seq,tile_size):
    """
    Given the indices of star catalog tile files, calculate the spherical rectangles corresponding to the indices.

    Usage:
        >>> radec_box,box_center = seq2radec(100,3)
        >>> radec_box,box_center = seq2radec([120,130],5)

    Inputs:
        seqs -> [int,array_like] Index of the star catalog tile file.
        tile_size -> [int] Size of tile in [deg].
    Outputs:
        radec_box -> [int,array_like] spherical rectangles in format of [ra_min,dec_min,ra_max,dec_max], where
            ra_min -> [float] Left border of RA in [deg].
            dec_min -> [float] Lower border of DEC in [deg].
            ra_max -> [float] Right border of RA in [deg].
            dec_max -> [float] Upper border of DEC in [deg].
        box_center -> [float,array_like] Center of spherical rectangle in format of [ra,dec] in [deg]
    """
    if type(seq) is list: seq = np.array(seq)

    count_lon = 360//tile_size
    ra_min = seq%count_lon*tile_size
    ra_max = ra_min + tile_size
    codec_min = seq//count_lon*tile_size
    codec_max = codec_min + tile_size
    dec_min = 90 - codec_max
    dec_max = 90 - codec_min

    radec_box = np.stack([ra_min,dec_min,ra_max,dec_max]).T
    box_center = np.stack([(ra_min + ra_max)/2,(dec_min + dec_max)/2]).T
    return radec_box,box_center

def box2seqs(radec_box,tile_size):
    """
    Given a rectangle search area, calculate the corresponding indices of the star catalog tile files over the search area.

    Usage:
        >>> seqs = box2seqs([350.6,77.7,373.1,85.4],2)

    Inputs:
        radec_box -> [int,array_like] Rectangular search area in format of [ra_min,dec_min,ra_max,dec_max], where
            ra_min -> [float] Left border of RA in [deg].
            dec_min -> [float] Lower border of DEC in [deg].
            ra_max -> [float] Right border of RA in [deg].
            dec_max -> [float] Upper border of DEC in [deg].
        tile_size -> [int] Size of the tile in [deg]

    Outputs:
        seqs -> [array of int] Indices of the star catalog tile files over the rectangular search area.
    """
    tol = 1e-8 # Set the boundary tolerance in [deg]

    ra_min,dec_min,ra_max,dec_max = radec_box

    if ra_min >= ra_max or dec_min >= dec_max:
        raise ValueError('The rectangular area on the celestial sphere must start at the lower left corner and end at the upper right corner.')

    codec_min = 90 - dec_max
    codec_max = 90 - dec_min

    ra_seqs =  np.arange(int(ra_min//tile_size),int((ra_max - tol)//tile_size)+1)
    codec_seqs = np.arange(int(codec_min//tile_size),int((codec_max - tol)//tile_size)+1)

    # The discontinuity caused by crossing the primary meridian is solved by add '(ra_seqs < 0)*count_lon - (ra_seqs >= count_lon)*count_lon'
    count_lon = 360//tile_size
    seqs = codec_seqs[:,None]*count_lon + ra_seqs + (ra_seqs < 0)*count_lon - (ra_seqs >= count_lon)*count_lon

    return seqs.flatten()

def cone2seqs(ra_c,dec_c,radius,tile_size):
    """
    Given a cone(spherical cap) search area, calculate the corresponding indices of the star catalog tile files over the search area.

    Usage:
        >>> seqs = cone2seqs(100,20,16,2)

    Inputs:
        ra_c -> [float] Center of the cap in RA, in [deg].
        dec_c -> [float] Center of the cap in DEC, in [deg].
        radius -> [float] Angular radius of the cap, in [deg].
        tile_size -> [int] Size of tile in [deg]. Avaliable values are 1,2,3,5,6,9,10.

    Outputs:
        seqs -> [array of int] Indices of the star catalog tile files over the cone search area.
    """
    count_lon = 360//tile_size
    radius += tile_size*1.5 # buffer of boundary
    N = int(180/tile_size)
    if N%2: raise Exception('tile_size must satisfy the condition that 180/tile_size is even.')
    L = int(N/2) - 1
    mask_cap = from_cap(radius, dec_c, ra_c, L)
    dec_index,ra_index = np.where(mask_cap)
    seqs = dec_index * count_lon + ra_index
    return seqs

def _load_files(sc_indices,sc_path,sc_name,_mode):
    """
    Build a generator for loading multiple star catalog tile files.

    Usage:
        >>> _load_files([10,15,178,3430,8009,10002],'starcatalogs/raw/hygv35/res5/','hygv35,'raw')

    Inputs:
        sc_indices -> [array of int] Indices of the star catalog tile files to load.
        sc_path -> [str] Path of starcatalog tile files, such as 'starcatalogs/raw/hygv35/res5/'
        sc_name -> [str] Name of the starcatalog. Available starcatalogs include 'hygv35', 'gsc12', 'gsc242', 'gaiadr3', '2mass', 'ucac5', 'usnob', etc.
        _mode -> [str] Types of star catalogs, including 'raw', 'reduced', 'simplified', where
            'raw' represents the original star catalog, which contains all information about the star
            'reduced' represents the reduced star catalog, which contains the position, proper motion, apparent magnitude, epoch of the star
            'simplified' represents the minimalist star catalog, which only includes the position and apparent magnitude of stars
    Outputs:
        A generator
    """
    if _mode == 'raw':
        skiprows = 1
        # raw模式：跳过第一行，pandas默认从跳过后的第一行推断表头
        names = None
    elif _mode == 'simplified':
        # Simplified模式CSV文件没有表头，需要指定列名
        skiprows = 0
        names = ['ra', 'dec', 'mag']
    else:
        # reduced模式：可能有表头，使用默认推断
        skiprows = 0
        names = None

    prefix = _resolve_tile_csv_prefix(sc_path, sc_name)
    base_dir = _catalog_tile_dir(sc_path)

    for sc_index in sc_indices:
        filename = base_dir + prefix + "-" + str(sc_index) + ".csv"
        # Skip missing or empty tiles; short one-star rows are still valid.
        if not os.path.isfile(filename):
            continue
        if os.path.getsize(filename) == 0:
            continue
        if _mode == 'simplified':
            # simplified模式：明确指定header=None和列名
            yield pd.read_csv(filename, skiprows=skiprows, dtype=str, header=None, names=names)
        else:
            # raw和reduced模式：使用默认的header='infer'行为
            yield pd.read_csv(filename, skiprows=skiprows, dtype=str)

def search_box_magpm(radec_box,sc_path,sc_name,tile_size,_mode,mag_threshold,t_pm):
    """
    Perform a rectangle search of stars on the reduced star catalog.

    Usage:
        >>> df = search_box([20,30,30,40],'starcatalogs/reduced/hygv35/res5/','hygv35',5,'reduced',8,2023.5)

    Inputs:
        radec_box -> [int,array_like] Rectangular search area in format of [ra_min,dec_min,ra_max,dec_max], where
            ra_min -> [float] Left border of RA in [deg].
            dec_min -> [float] Lower border of DEC in [deg].
            ra_max -> [float] Right border of RA in [deg].
            dec_max -> [float] Upper border of DEC in [deg].
        sc_path -> [str] Path of starcatalog tile files, such as 'starcatalogs/reduced/hygv35/'
        sc_name -> [str] Name of the starcatalog. Available starcatalogs include 'hygv35', 'gsc12', 'gsc242', 'gaiadr3', '2mass', 'ucac5', 'usnob', etc.
        tile_size -> [int] Size of the tile in [deg]
        _mode -> [str] Types of star catalogs, including 'raw', 'reduced', 'simplified', where
            'raw' represents the original star catalog, which contains all information about the star
            'reduced' represents the reduced star catalog, which contains the position, proper motion, apparent magnitude, epoch of the star
            'simplified' represents the minimalist star catalog, which only includes the position and apparent magnitude of stars
        mag_threshold -> [float] Apparent magnitude limit of the detector
        t_pm -> [float] The epoch when the search was performed

    Outputs:
        Dataframe for stars within the rectangule search area.
    """
    ra_min,dec_min,ra_max,dec_max = radec_box
    sc_indices = box2seqs(radec_box,tile_size)
    df = pd.concat(_load_files(sc_indices,sc_path,sc_name,_mode))
    df.drop_duplicates(subset=['ra','dec'],inplace=True)

    if {'pmra', 'pmdec'}.issubset(df.columns):
         df[['ra','dec','pmra','pmdec','mag','epoch']] = df[['ra', 'dec','pmra','pmdec','mag','epoch']].apply(pd.to_numeric)
    else:
        df[['ra','dec','mag','epoch']] = df[['ra','dec','mag','epoch']].apply(pd.to_numeric)

    mag_flag = (df['mag'] < mag_threshold)
    df = df[mag_flag].sort_values(by=['mag'])
    epoch = df['epoch']

    # calculate proper motion
    dt = t_pm - epoch

    if {'pmra', 'pmdec'}.issubset(df.columns):
        df['ra'] +=  df['pmra']/3.6e6 * dt
        df['dec'] += df['pmdec']/3.6e6 * dt
    else:
        warnings.warn('Proper motion data for stars in catalog {:s} are not found.'.format(scname))

    ra,dec = df['ra'],df['dec']
    ra_flag = np.abs(ra - (ra_min + ra_max)/2) < (ra_max - ra_min)/2
    dec_flag = np.abs(dec- (dec_min + dec_max)/2) < (dec_max - dec_min)/2

    flag = ra_flag & dec_flag
    df = df[flag]
    df['epoch'] = t_pm

    return df.reset_index(drop=True)

def search_cone_magpm(center,radius,sc_path,sc_name,tile_size,_mode,mag_threshold,t_pm):
    """
    Perform a cone search of stars on the reduced star catalog.

    Usage:
        >>> df = search_cone([20,30],10,'starcatalogs/reduced/hygv35/res5/','hygv35',5,'reduced',8,2023.5)

    Inputs:
        center -> [int,array_like] Center of the cap in format of [ra_c,dec_c], where
            ra_c -> [float] RA, in [deg].
            dec_c -> [float] DEC, in [deg].
        radius -> [float] Angular radius of the cap, in [deg].
        sc_path -> [str] Path of starcatalog tile files, such as 'starcatalogs/reduced/hygv35/'
        sc_name -> [str] Name of the starcatalog. Available starcatalogs include 'hygv35', 'gsc12', 'gsc242', 'gaiadr3', '2mass', 'ucac5', 'usnob', etc.
        tile_size -> [int] Size of the tile in [deg]. Avaliable values are 1,2,3,5,6,9,10.
        _mode -> [str] Types of star catalogs, including 'raw', 'reduced', 'simplified', where
            'raw' represents the original star catalog, which contains all information about the star
            'reduced' represents the reduced star catalog, which contains the position, proper motion, apparent magnitude, epoch of the star
            'simplified' represents the minimalist star catalog, which only includes the position and apparent magnitude of stars
        mag_threshold -> [float] Apparent magnitude limit of the detector
        t_pm -> [float] The epoch when the search was performed

    Outputs:
        Dataframe for stars within the cone search area.
    """
    ra_c,dec_c = center
    sc_indices = cone2seqs(ra_c,dec_c,radius,tile_size)
    df = pd.concat(_load_files(sc_indices,sc_path,sc_name,_mode))
    df.drop_duplicates(subset=['ra','dec'],inplace=True)

    if {'pmra', 'pmdec'}.issubset(df.columns):
         df[['ra','dec','pmra','pmdec','mag','epoch']] = df[['ra', 'dec','pmra','pmdec','mag','epoch']].apply(pd.to_numeric)
    else:
        df[['ra','dec','mag','epoch']] = df[['ra','dec','mag','epoch']].apply(pd.to_numeric)

    mag_flag = (df['mag'] < mag_threshold)
    df = df[mag_flag].sort_values(by=['mag'])

    # calculate proper motion
    dt = t_pm - df['epoch']

    if {'pmra', 'pmdec'}.issubset(df.columns):
        df['ra'] +=  df['pmra']/3.6e6 * dt
        df['dec'] += df['pmdec']/3.6e6 * dt
    else:
        warnings.warn('Proper motion data for stars in catalog {:s} are not found.'.format(scname))

    ra,dec = df['ra'],df['dec']
    c1 = SkyCoord(ra,dec, unit='deg')
    c2 = SkyCoord(ra_c,dec_c, unit='deg')
    sep = c1.separation(c2).deg

    flag = sep < radius
    df = df[flag]
    df['epoch'] = t_pm

    return df.reset_index(drop=True)

def search_box(radec_box,sc_path,sc_name,tile_size,_mode):
    """
    Perform a rectangle search of stars on the simplified star catalog.

    Usage:
        >>> df = search_box([20,30,30,40],'starcatalogs/simplified/hygv35/res5/mag8.0/epoch2023.0/','hygv35',5,'simplified')

    Inputs:
        radec_box -> [int,array_like] Rectangular search area in format of [ra_min,dec_min,ra_max,dec_max], where
            ra_min -> [float] Left border of RA in [deg].
            dec_min -> [float] Lower border of DEC in [deg].
            ra_max -> [float] Right border of RA in [deg].
            dec_max -> [float] Upper border of DEC in [deg].
        sc_path -> [str] Path of starcatalog tile files, such as 'starcatalogs/reduced/hygv35/'
        sc_name -> [str] Name of the starcatalog. Available starcatalogs include 'hygv35', 'gsc12', 'gsc242', 'gaiadr3', '2mass', 'ucac5', 'usnob', etc.
        tile_size -> [int] Size of the tile in [deg]
        _mode -> [str] Types of star catalogs, including 'raw', 'reduced', 'simplified', where
            'raw' represents the original star catalog, which contains all information about the star
            'reduced' represents the reduced star catalog, which contains the position, proper motion, apparent magnitude, epoch of the star
            'simplified' represents the minimalist star catalog, which only includes the position and apparent magnitude of stars

    Outputs:
        Dataframe for stars within the rectangule search area.
    """
    sc_indices = box2seqs(radec_box,tile_size)
    frames = list(_load_files(sc_indices,sc_path,sc_name,_mode))
    if not frames:
        return pd.DataFrame(columns=["ra", "dec", "mag"], dtype=float)
    df = pd.concat(frames)
    df.drop_duplicates(subset=['ra','dec'],inplace=True)

    df[['ra','dec','mag']] = df[['ra','dec','mag']].apply(pd.to_numeric)

    ra_min,dec_min,ra_max,dec_max = radec_box
    ra_flag = np.abs(df['ra'] - (ra_min + ra_max)/2) < (ra_max - ra_min)/2
    dec_flag = np.abs(df['dec']- (dec_min + dec_max)/2) < (dec_max - dec_min)/2

    flag = ra_flag & dec_flag
    df = df[flag].sort_values(by=['mag'])

    return df.reset_index(drop=True)

def search_cone(center,radius,sc_path,sc_name,tile_size,_mode):
    """
    Perform a cone search of stars on the simplified star catalog.

    Usage:
        >>> df = search_cone([20,30],10,'starcatalogs/simplified/hygv35/res5/mag8.0/epoch2023.0/','hygv35',5,'simplified')

    Inputs:
        center -> [int,array_like] Center of the cap in format of [ra_c,dec_c], where
            ra_c -> [float] RA, in [deg].
            dec_c -> [float] DEC, in [deg].
        radius -> [float] Angular radius of the cap, in [deg].
        sc_path -> [str] Path of starcatalog tile files, such as 'starcatalogs/reduced/hygv35/'
        sc_name -> [str] Name of the starcatalog. Available starcatalogs include 'hygv35', 'gsc12', 'gsc242', 'gaiadr3', '2mass', 'ucac5', 'usnob', etc.
        tile_size -> [int] Size of the tile in [deg]. Avaliable values are 1,2,3,5,6,9,10.
        _mode -> [str] Types of star catalogs, including 'raw', 'reduced', 'simplified', where
            'raw' represents the original star catalog, which contains all information about the star
            'reduced' represents the reduced star catalog, which contains the position, proper motion, apparent magnitude, epoch of the star
            'simplified' represents the minimalist star catalog, which only includes the position and apparent magnitude of stars

    Outputs:
        Dataframe for stars within the cone search area.

    调试: 设置环境变量 ``STARCATALOG_QUERY_DEBUG=1`` 可在 stderr 打印加载行数、天区范围、
    角距分位数与 ``sep < radius`` 保留条数，用于排查本函数末尾锥形过滤后变空的原因。
    """
    ra_c,dec_c = center
    sc_indices = cone2seqs(ra_c,dec_c,radius,tile_size)
    frames = list(_load_files(sc_indices,sc_path,sc_name,_mode))
    if not frames:
        return pd.DataFrame(columns=["ra", "dec", "mag"], dtype=float)
    df = pd.concat(frames)
    df.drop_duplicates(subset=['ra','dec'],inplace=True)

    df[['ra','dec','mag']] = df[['ra','dec','mag']].apply(pd.to_numeric)

    c1 = SkyCoord(df['ra'],df['dec'], unit='deg')
    c2 = SkyCoord(ra_c,dec_c, unit='deg')
    sep = c1.separation(c2).deg
    sep_deg = np.asarray(sep, dtype=float)

    _dbg = os.environ.get("STARCATALOG_QUERY_DEBUG", "").strip().lower() in (
        "1",
        "true",
        "yes",
    )
    if _dbg:
        import sys

        n = len(df)
        n_bad = int(df[["ra", "dec"]].isna().any(axis=1).sum()) if n else 0
        tiles_n = int(len(np.unique(np.asarray(sc_indices).ravel())))
        if n:
            r0, r1 = float(df["ra"].min()), float(df["ra"].max())
            d0, d1 = float(df["dec"].min()), float(df["dec"].max())
            s0, s1 = float(np.nanmin(sep_deg)), float(np.nanmax(sep_deg))
            sm = float(np.nanmedian(sep_deg))
            nin = int(np.sum(sep_deg < radius))
        else:
            r0 = r1 = d0 = d1 = s0 = s1 = sm = float("nan")
            nin = 0
        sys.stderr.write(
            "[starcatalogquery.search_cone] center=({:.6f},{:.6f}) deg, radius={:.6f} deg, "
            "tile_size={}\n".format(ra_c, dec_c, radius, tile_size)
        )
        sys.stderr.write(
            "  tiles_hit(unique)={}, rows_loaded={}, rows_nan_ra_or_dec={}\n".format(
                tiles_n, n, n_bad
            )
        )
        if n:
            sys.stderr.write(
                "  loaded_ra_deg[min,max]=[{:.4f},{:.4f}] loaded_dec_deg[min,max]=[{:.4f},{:.4f}]\n".format(
                    r0, r1, d0, d1
                )
            )
        sys.stderr.write(
            "  sep_deg[min,max,median]=[{:.4f},{:.4f},{:.4f}], rows(sep<radius)={}\n".format(
                s0, s1, sm, nin
            )
        )

    flag = sep_deg < radius
    df = df[flag].sort_values(by=['mag'])

    return df.reset_index(drop=True)
