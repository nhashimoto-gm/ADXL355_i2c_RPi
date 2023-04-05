import smbus
import time

# ADXL355のI2Cアドレス
ADXL355_ADDRESS = 0x1D

# I2Cバスの初期化
bus = smbus.SMBus(1)

# ADXL355の設定
bus.write_byte_data(ADXL355_ADDRESS, 0x28, 0x0A)  # レンジ設定 +/- 2g
bus.write_byte_data(ADXL355_ADDRESS, 0x2C, 0x08)  # 高解像度モード

# 加速度の読み取り
def read_acceleration():
    # X軸データの読み取り
    x_data = bus.read_i2c_block_data(ADXL355_ADDRESS, 0x08, 3)
    x = (x_data[0] << 16 | x_data[1] << 8 | x_data[2]) >> 4
    if x & 0x80000:
        x |= 0xFFF00000
    x = x * 2.0 / 524288.0  # レンジに応じてスケールを調整

    # Y軸データの読み取り
    y_data = bus.read_i2c_block_data(ADXL355_ADDRESS, 0x0B, 3)
    y = (y_data[0] << 16 | y_data[1] << 8 | y_data[2]) >> 4
    if y & 0x80000:
        y |= 0xFFF00000
    y = y * 2.0 / 524288.0  # レンジに応じてスケールを調整

    # Z軸データの読み取り
    z_data = bus.read_i2c_block_data(ADXL355_ADDRESS, 0x0E, 3)
    z = (z_data[0] << 16 | z_data[1] << 8 | z_data[2]) >> 4
    if z & 0x80000:
        z |= 0xFFF00000
    z = z * 2.0 / 524288.0  # レンジに応じてスケールを調整

    return x, y, z

# メインループ
while True:
    x, y, z = read_acceleration()
    print("X軸加速度: {:.3f}g, Y軸加速度: {:.3f}g, Z軸加速度: {:.3f}g".format(x, y, z))
    time.sleep(0.1)
