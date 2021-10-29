import numpy as np

"""
Generic WARLS packet encoding
Max LEDs: 255

Header: [1, timeout]
Byte 	Description
2 + n*4 	LED Index
3 + n*4 	Red Value
4 + n*4 	Green Value
5 + n*4 	Blue Value
"""
def build_warls_packet(data: np.ndarray, timeout: int, last_frame: np.array):
    packet = bytearray([1, (timeout or 1)])

    byteData = data.astype(np.dtype("B"))

    if last_frame is None or data.shape != last_frame.shape:
        last_frame = np.full(data.shape ,np.nan)
    '''
    for i in range(len(byteData)): # loop through byteData
        if not np.array_equal(last_bytes[i], byteData[i]): # if index has changed from last sent frame
            packet.extend(bytes([i]))   # add index as first byte
            packet.extend(byteData[i].flatten().tobytes())
    ''' # do above in numpy
    # get indexes of pixels that have changed
    idx=np.flatnonzero(np.any(last_frame!=data, axis=1))
    # make a new output array
    out=np.zeros((len(idx), 4), dtype="B")
    # first byte of each pixel is the index
    out[:,0] = idx
    # final three bytes are the pixel values
    out[:,1:] = byteData[idx]
    # convert out to bytes to send
    packet.extend(out.flatten().tobytes())
    return packet

"""
Generic DRGB packet encoding
Max LEDs: 490

Header: [2, timeout]
Byte 	Description
2 + n*3 	Red Value
3 + n*3 	Green Value
4 + n*3 	Blue Value

"""
def build_drgb_packet(data: np.ndarray, timeout: int):
    packet = bytearray([2, (timeout or 1)])

    byteData = data.astype(np.dtype("B"))
    packet.extend(byteData.flatten().tobytes())
    return packet

'''
Generic DRGBW packet encoding
Max LEDs: 367

Header: [3, timeout]
Byte 	Description
2 + n*3 	Red Value
3 + n*3 	Green Value
4 + n*3 	Blue Value
5 + n*4 	White Value
'''
def build_drgbw_packet(data: np.ndarray, timeout: int):
    packet = bytearray([3, (timeout or 1)])

    byteData = data.astype(np.dtype("B"))
    out = np.zeros((len(byteData), 4), dtype="B")
    out[:,:3] = byteData
    # 4th column is unusued white channel -> 0
    packet.extend(out.flatten().tobytes())


    # for i in range(len(byteData)):
    #     packet.extend(byteData[i].flatten().tobytes())
    #     packet.extend(bytes(0)) 
    return packet


"""
Generic DNRGB packet encoding
Max LEDs: 489 / packet

Header: [4, timeout, start index high byte, start index low byte]
Byte 	Description
4 + n*3 	Red Value
5 + n*3 	Green Value
6 + n*3 	Blue Value
"""
def build_dnrgb_packet(data: np.ndarray, timeout: int, led_start_index: np.uint16):
    packet = bytearray([4, (timeout or 1), (led_start_index >> 8),(led_start_index & 0x00ff)]) # high byte, then low byte

    byteData = data.astype(np.dtype("B"))
    packet.extend(byteData.flatten().tobytes())
    return packet

"""
Generic Adalight serial packet encoding

Header: [A, d, a, pixel count high byte, pixel count low byte, pixel count checksum]
Byte 	Description
4 + n*3 	Red Value
5 + n*3 	Green Value
6 + n*3 	Blue Value
"""
def build_adalight_packet(data: np.ndarray, color_order: str):
    pixel_length = len(data)
    packet = bytearray([ord("A"), ord("d"), ord("a"), (pixel_length >> 8),(pixel_length & 0x00ff)]) # high byte, then low byte
    packet.extend([packet[3] ^ packet[4] ^ 0x55]) # checksum

    byteData = data.astype(np.dtype("B"))
    # if color_order == "RGB": pass
    if color_order == "GRB":
        byteData[:, [1, 0]] = byteData[:, [0, 1]] # swap columns
    elif color_order == "BGR":
        byteData[:, [2, 0]] = byteData[:, [0, 2]]
    elif color_order == "RBG":
        byteData[:, [2, 1]] = byteData[:, [1, 2]]
    elif color_order == "BRG":
        byteData[:, [2, 0]] = byteData[:, [0, 2]]
        byteData[:, [2, 1]] = byteData[:, [1, 2]]
    elif color_order == "GBR":
        byteData[:, [2, 0]] = byteData[:, [0, 2]]
        byteData[:, [1, 0]] = byteData[:, [0, 1]]
    packet.extend(byteData.flatten().tobytes())
    return packet
