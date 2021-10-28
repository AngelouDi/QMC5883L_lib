REG_X_LSB = 0x00
REG_X_MSB = 0x01
REG_Y_LSB = 0x02
REG_Y_MSB = 0x03
REG_Z_LSB = 0x04
REG_Z_MSB = 0x05
REG_STAT1 = 0x06
REG_TMP_LSB = 0x07
REG_TMP_MSB = 0x08
REG_CTRL1 = 0x09
REG_CTRL2 = 0x0A

MODE_SBY = 0b00
MODE_CON = 0b01

ODR_010 = 0b00 << 2
ODR_050 = 0b01 << 2
ODR_100 = 0b10 << 2
ODR_200 = 0b11 << 2

RNG_2G = 0b00 << 4
RNG_8G = 0b01 << 4

OSR_512 = 0b00 << 6
OSR_256 = 0b01 << 6
OSR_128 = 0b10 << 6
OSR_64 = 0b11 << 6

SOFT_RST = 0x80


def print_in_bits(byte):
    bits = []
    if type(byte).__name__ == "bytes":
        byte = int.from_bytes(byte, "little")
    for i in range(0, 8):
        bits.append(byte >> 7 - i & 1)
    print(bits)


def print_in_bits16(byte):
    if type(byte).__name__ == "bytes":
        byte = int.from_bytes(byte, "little")
    bits = []
    for i in range(0, 16):
        try:
            bits.append(byte >> (15 - i) & 1)
        except ValueError:
            pass
    print(bits)


def twoscomplement_to_dec(twos):
    dec = 0
    for i in range(0, 14):
        dec += (twos >> i & 1) * 2 ** i
    return dec


def setup_control_register(i2c, device_id, osr, rng, odr, continuous):
    ctrl1_register = 0b00000000

    if osr == 256:
        ctrl1_register |= OSR_256
    elif osr == 128:
        ctrl1_register |= OSR_128
    elif osr == 64:
        ctrl1_register |= OSR_64
    else:
        ctrl1_register |= OSR_512

    if rng == 2:
        ctrl1_register |= RNG_2G
    else:
        ctrl1_register |= RNG_8G

    if odr == 10:
        ctrl1_register |= ODR_010
    elif odr == 100:
        ctrl1_register |= ODR_100
    elif odr == 200:
        ctrl1_register |= ODR_200
    else:
        ctrl1_register |= ODR_050

    if continuous:
        ctrl1_register |= MODE_CON
    else:
        ctrl1_register |= MODE_SBY

    ctrl1_register = ctrl1_register.to_bytes(2, 'little')

    i2c.writeto_mem(device_id, REG_CTRL1, ctrl1_register)


def get_status(i2c, device_id):
    status = i2c.readfrom_mem(device_id, REG_STAT1, 1)
    status = int.from_bytes(status, "little")
    DRDY = status & 1 == 1
    OVL = status >> 1 & 1 == 1
    DOR = status >> 2 & 1 == 1

    return {"DRDY": DRDY, "OVL": OVL, "DOR": DOR}


def get_data(i2c, device_id, rng):
    data = i2c.readfrom_mem(device_id, REG_X_LSB, 6)

    x_lsb = data[REG_X_LSB]
    x_msb = data[REG_X_MSB]
    y_lsb = data[REG_Y_LSB]
    y_msb = data[REG_Y_MSB]
    z_lsb = data[REG_Z_LSB]
    z_msb = data[REG_Z_MSB]

    x = x_msb << 8 | x_lsb
    y = y_msb << 8 | y_lsb
    z = z_msb << 8 | z_lsb

    x = twoscomplement_to_dec(x)
    y = twoscomplement_to_dec(y)
    z = twoscomplement_to_dec(z)

    if rng == 2:
        x = twoscomplement_to_dec(x) / 12000
        y = twoscomplement_to_dec(y) / 12000
        z = twoscomplement_to_dec(z) / 12000
    else:
        x = twoscomplement_to_dec(x) / 3000
        y = twoscomplement_to_dec(y) / 3000
        z = twoscomplement_to_dec(z) / 3000

    print({"x": x, "y": y, "z": z})
    return {"x": x, "y": y, "z": z}


def get_temp(i2c, id=0xd):
    tmp_lsb = int.from_bytes(i2c.readfrom_mem(id, REG_TMP_LSB, 1), "little")
    tmp_msb = int.from_bytes(i2c.readfrom_mem(id, REG_TMP_MSB, 1), "little")

    print_in_bits(tmp_lsb)
    print_in_bits(tmp_msb)
    tmp = tmp_msb << 8 | tmp_lsb

    tmp = twoscomplement_to_dec(tmp) / 100
    print(tmp)


class QMC5883L:

    def __init__(self, i2c, device_id=0xD, continuous=True, odr=50, rng=8, osr=512, reset=True):
        self.i2c = i2c
        self.device_id = device_id
        self.continuous = continuous
        self.odr = odr
        self.rng = rng
        self.osr = osr
        self.reset = reset
        self.magnet_data = {"x": 0, "y": 0, "z": 0}

    def init(self):
        if self.reset:
            self.soft_reset()
        setup_control_register(i2c=self.i2c, device_id=self.device_id, osr=self.osr, rng=self.rng, odr=self.odr,
                               continuous=self.continuous)

    def soft_reset(self):
        self.i2c.writeto_mem(self.device_id, REG_CTRL2, SOFT_RST.to_bytes(2, 'little'))

    def get_magnet_data(self, wait=False):
        while True:
            if get_status(i2c=self.i2c, device_id=self.device_id)["DRDY"]:
                self.magnet_data = get_data(i2c=self.i2c, device_id=self.rng, rng=self.rng)
                return self.magnet_data
            if not wait:
                return self.magnet_data

