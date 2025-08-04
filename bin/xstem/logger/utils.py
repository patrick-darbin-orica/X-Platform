reference_voltage = 1.278654563
reference_water_contact = 0.475634483
reference_td_voltage = 6.224025124

def calibrate_tension(x):
    dV = reference_voltage - x
    dmV = dV * 1000
    kgs = (0.1691 * dmV) + 0.0995
    return kgs

def calibrate_water_contact(x):
    return round((x - reference_water_contact) / 2.0 ,2)

def calibrate_td_contact(x):
    return round((reference_td_voltage - x) / 2.5, 2)

def calculate_line_depth(total_rotations):
    return total_rotations * -1