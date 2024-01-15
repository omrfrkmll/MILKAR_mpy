"""Waveshare Pico LCD 1.3 inch display"""

from machine import Pin, SPI
import st7789

TFA = 0   # top free area when scrolling
BFA = 80# bottom free area when scrolling

def config(rotation=3, buffer_size=0, options=0):
    return st7789.ST7789(
        SPI(1, baudrate=62500000, sck=Pin(10), mosi=Pin(11)),
        240,
        240,
        reset=Pin(14, Pin.OUT),
        cs=Pin(13, Pin.OUT),
        dc=Pin(12, Pin.OUT),
        backlight=Pin(15, Pin.OUT))