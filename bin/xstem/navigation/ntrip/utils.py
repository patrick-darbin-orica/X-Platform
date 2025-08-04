from pyproj import Transformer
import numpy as np

def compute_enu_offset(x_ref, y_ref, z_ref, x_recv, y_recv, z_recv, datum_ref="NAD83", datum_recv="WGS84"):
    """
    Compute the ENU offset from a reference station to a receiver using specified datums.

    Parameters:
    - x_ref, y_ref, z_ref: ECEF coordinates of the reference station (in meters)
    - x_recv, y_recv, z_recv: ECEF coordinates of the receiver (in meters)
    - datum_ref: Datum for the reference station ('NAD83', 'ITRF2014', 'WGS84')
    - datum_recv: Datum for the receiver ('NAD83', 'ITRF2014', 'WGS84')

    Returns:
    - Tuple of (east, north, up) offsets in meters
    """
    datum_epsg = {
        "NAD83": "epsg:4269",
        "ITRF2014": "epsg:7789",
        "WGS84": "epsg:4326"
    }

    datum_ref = datum_ref.upper()
    datum_recv = datum_recv.upper()

    if datum_ref not in datum_epsg or datum_recv not in datum_epsg:
        raise ValueError("Unsupported datum. Choose from 'NAD83', 'ITRF2014', or 'WGS84'.")

    # Convert reference ECEF to geodetic using reference datum
    transformer_to_geodetic_ref = Transformer.from_crs("epsg:4978", datum_epsg[datum_ref], always_xy=True)
    lon_ref, lat_ref, _ = transformer_to_geodetic_ref.transform(x_ref, y_ref, z_ref)

    # Compute delta in ECEF
    dx = x_recv - x_ref
    dy = y_recv - y_ref
    dz = z_recv - z_ref

    # Rotation matrix from ECEF to ENU
    lat_rad = np.radians(lat_ref)
    lon_rad = np.radians(lon_ref)

    R = np.array([
        [-np.sin(lon_rad),              np.cos(lon_rad),               0],
        [-np.sin(lat_rad)*np.cos(lon_rad), -np.sin(lat_rad)*np.sin(lon_rad), np.cos(lat_rad)],
        [np.cos(lat_rad)*np.cos(lon_rad),  np.cos(lat_rad)*np.sin(lon_rad),  np.sin(lat_rad)]
    ])

    enu = R @ np.array([dx, dy, dz])
    return tuple(enu)


if __name__ == "__main__":
    real = (-22632.7178, -6346.4788, -42.6021)
    
    
    rtk = (-667738.1680000001, -5477291.0093, 3188605.3364000004)
    recv = (-690583.4704999999, -5477683.922, 3183097.1281999997)

    enu = compute_enu_offset(rtk[0], rtk[1], rtk[2], recv[0], recv[1], recv[2], datum_ref="WGS84", datum_recv="NAD83")

    print(enu)
    
    error = (enu[0] - real[0], enu[1] - real[1], enu[2] - real[2])

    print(error)