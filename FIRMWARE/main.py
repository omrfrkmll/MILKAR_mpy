# this project has been written  by ILTERAY for MEKAR company
__device_model__="MILKAR"
__version__ = "2.1.0"
import time
import os
from time import sleep
import machine
import json
import math
import gc
from machine import Pin, SPI, ADC
from mfrc522 import MFRC522
from hx711_pio import HX711
import st7789
import tft_config
from fonts import vga2_bold_16x32 as font
from machine import Timer
machine.freq(250000000)
# hx711 pin definitions
pin_OUT = Pin(7, Pin.IN, pull=Pin.PULL_DOWN)
pin_SCK = Pin(6, Pin.OUT)
hx711 = HX711(pin_SCK, pin_OUT)
# ----------------#
gc.enable()
"""termistor pin tanimlama"""
thermistor = machine.ADC(26)
"""screen spi begin"""
tft = tft_config.config(1)
tft.init()
"""card reader spi begin"""
reader = MFRC522(spi_id=0, sck=2, miso=4, mosi=3, cs=1, rst=0)
""" Setup the Rotary Encoder"""
sw_pin = Pin(16, Pin.IN, Pin.PULL_UP)
clk_pin = Pin(17, Pin.IN, Pin.PULL_UP)
dt_pin = Pin(18, Pin.IN, Pin.PULL_UP)
previous_value = True
button_down = False
""""cooler & mixer pin definition"""
cooler_pin = Pin(20, Pin.OUT)
mixer_pin = Pin(21, Pin.OUT)
"""constants"""
width = 240
height = 240
line = 1
highlight = 1
shift = 0
list_length = 0
previous_C = 0
previous_gr = 0
previous_ml = 0
steinhart_y = 60
weight_y = steinhart_y + 45
liter_y = weight_y + 45

mixer_state = False
temp_treshould_state = False
last_toggle_time = time.ticks_ms()

access = False
def timer_callback(t):
    global access
    access = False
timer = Timer(period=300000, mode=Timer.PERIODIC, callback=timer_callback)

with open('config.json', 'r') as f:  # read the json file
    config = json.load(f)
def open_language_file(language,change=None):# read language packet
    global lang
    if change:
        del lang
    with open(f'languages/{language}.json', 'r') as l:
        lang = json.load(l)
    return lang

open_language_file(config["language"])# get language packet

def write_config(a=config):
    with open('config.json', 'w') as f:
        json.dump(config, f)

def center_text(y, text, font, fgcolor=st7789.WHITE,bgcolor=st7789.BLACK):
    global center, w,text_last
    w = 1 if isinstance(text, int) else len(text)
    center=(tft.width() // 2) - ((w * font.WIDTH) // 2 )
    text_last =(tft.width() // 2) + ((w * font.WIDTH) // 2 )
    tft.text(font,text,center,y,fgcolor,bgcolor)
    return center,text_last

def draw_image(image_path, x, y, width=None, height=None):
    tft.jpg(image_path, x, y)


def home():
    global text
    tft.fill(st7789.BLACK) 
    if cooler_pin.value() == 0:
        draw_image('assets/cooler-pasive.jpg', 0, 0)  # cooler off icon
    elif cooler_pin.value() == 1:
        draw_image('assets/cooler-active.jpg', 0, 0)  # cooler on icon
    if mixer_pin.value() == 0:
        draw_image('assets/mixer-pasive.jpg', 49, 0)  # mixer off icon
    elif mixer_pin.value() == 1:
        draw_image('assets/mixer-active.jpg', 49, 0)  # mixer on icon

def read_uids():
    with open("card_lib.dat") as f:
        lines = f.readlines()
    return [line.strip("\n") for line in lines]


def rfidread():
    global access
    tft.fill(st7789.BLACK)
    center_text(104, lang["scan_card"], font, st7789.color565(0, 255, 0))  # call for center the text
#     draw_image('assets/rfidread.jpg', 14, 14, 100, 100)
    rfid_timout = 0
    while rfid_timout <= 20:
        reader.init()
        (stat, tag_type) = reader.request(reader.REQIDL)
        if stat == reader.OK:
            (stat, uid) = reader.SelectTagSN()
            if stat == reader.OK:
                PreviousCard = uid
                try:
                    uids = read_uids()
                except BaseException:
                    uids = []
                if uid == '[211, 86, 206, 149]' or uid in uids:
                    access = True
                    rfiddone()
                    sleep(1)
                    gc.collect()
                    mainmenu()
                    rfid_timout=19
                else:
                    rfidno()
                    break
            else:
                pass
        else:
            PreviousCard = [0]
        rfid_timout += 1
        sleep(0.5)
    home()

def rfiddone():
    tft.fill(st7789.BLACK) 
    center_text(104, lang["card_read"], font, st7789.color565(72, 222, 105))  # call for center the text
#     draw_image('assets/rfiddone.jpg', 20, 40)

def rfidno():
    tft.fill(st7789.BLACK) 
    center_text(104,"GECERSIZ KART",font,st7789.color565(198,59,59))  # call for center the text
#     draw_image('assets/rfidno.jpg', 14, 20)
    sleep(2)
    home()

def draw_message(text):
    tft.fill_rect(0, 200, 240, 40, st7789.BLACK)
    tft.text(font,text, 0, 207, st7789.WHITE)

def temperature():
    global previous_C, steinhart
    temperature_reads = [thermistor.read_u16() for _ in range(5)]
    temperature_value = sum(temperature_reads) / len(temperature_reads)
    try:
        R = config['TH_RES'] / (65535 / temperature_value - 1) #10000 termistörün direnci
        steinhart = math.log(R / config['TH_RES']) / 3950.0 #10000 termistörün direnci
        steinhart += 1.0 / (25.0 + 273.15)
        steinhart = (1.0 / steinhart) - 273.15 + config['thermistor_offset']
        if previous_C != len(str(round(steinhart, 1))):
            center_text(steinhart_y, "             ", font)
        center_text( steinhart_y, str(round(steinhart, 1))+" c", font, fgcolor= st7789.GREEN)
        previous_C = len(str(round(steinhart, 1)))
        
        del temperature_reads
        return steinhart
    except BaseException:
        draw_message(lang["error"]+" [T1]")

def weight():
    global previous_gr, previous_ml
    weights = []
    for i in range(5):
        weights.append(
            ((hx711.read() /
              config['weight']['scale_factor']) -
                config['weight']['self_weight']))
    # okunan raw values degerlerinin ortalamasi alinir
    weight = round((sum(weights) / len(weights)))
    liter = round((weight / 1.033))

    if previous_gr != len(str(round(weight, 1))):
        center_text(weight_y,"              ",font,st7789.BLUE)  # call for center the text
    if previous_ml != len(str(round(weight, 1))):
        center_text(liter_y,"              ",font,st7789.BLUE)  # call for center the text
    center_text(weight_y,str(weight)+" kg",font,st7789.BLUE)  # call for center the text
    previous_gr = len(str(round(weight, 1)))
    center_text(liter_y,str(liter)+" L",font,st7789.color565(
            255,
            80,
            37))  # call for center the text
    previous_ml = len(str(round(weight, 1)))
    
    del weights


def mixer_toogle(current_time):
    global mixer_state, temp_treshould_state, last_toggle_time
    try:
        cooler_pin.value(0)
        if mixer_state == False and (current_time -last_toggle_time) >= (config['mixer']['mixerwork'] *60000):  # 60000 olacak
            mixer_pin.value(0)
            mixer_state = True
            last_toggle_time = current_time
            home()
        if mixer_state and (current_time - last_toggle_time) >= (config['mixer']['mixerwait'] *60000):
            mixer_pin.value(1)
            mixer_state = False
            last_toggle_time = current_time
            home()
    except Exception as e:
        print("toggle error:", e)


def set_value(a, value, min_value=None, max_value=None):
        tft.fill(st7789.BLACK) 
        global previous_value, button_down
        center_text(int((tft.height() - font.HEIGHT - 2) / 2),str(a), font, st7789.color565(0, 255, 0))
        while True:
            if previous_value != dt_pin.value():
                if dt_pin.value() == False:
                    if clk_pin.value() == False:
                        a -= value
                        a = round(a,-int(math.floor(math.log10(value))))
                        if min_value is not None and a <= min_value:
                            a = min_value
                        tft.fill(st7789.BLACK) 
                        center_text(int((tft.height() - font.HEIGHT - 2) / 2),str(a), font, st7789.color565(0, 255, 0))
                        time.sleep_ms(3)
                    else:
                        a += value
                        a = round(a,-int(math.floor(math.log10(value))))
                        if max_value is not None and a >= max_value:
                            a = max_value
                        tft.fill(st7789.BLACK) 
                        center_text(int((tft.height() - font.HEIGHT - 2) / 2),str(a), font, st7789.color565(0, 255, 0))
                        time.sleep_ms(3)
                previous_value = dt_pin.value()
            time.sleep_ms(1)
            if sw_pin.value() == False and not button_down:
                button_down = True
                write_config()
                time.sleep_ms(1)
                break
            time.sleep_ms(1)
            if sw_pin.value() and button_down:
                button_down = False
            time.sleep_ms(1)
        return a

"""--------------------------------------------------------------------------------"""
"""---------------------------------ABOUT------------------------------------------"""
"""--------------------------------------------------------------------------------"""


def about_page(cond):
    global button_down, previous_value

    def aboutpage():
        tft.fill(st7789.BLACK) 
        if cond:
            center_text(0, lang["about"], font, st7789.GREEN)
        center_text(70, __device_model__, font, st7789.RED)
        center_text(120, "MEKAR", font, st7789.RED)
        
        center_text(170, __version__, font, st7789.WHITE)

    aboutpage()
    previous_time = time.ticks_ms()

    while cond:
        try:
            gc.collect()
            current_time = time.ticks_ms()
            elapsed_time = current_time - previous_time
            # Check for encoder rotated
            if previous_value != dt_pin.value():
                previous_time = current_time
                if dt_pin.value() == False:
                    # Turned Left
                    if clk_pin.value() == False:
                        break
                    # Turned Right
                    else:
                        break
                previous_value = dt_pin.value()
            time.sleep_ms(1)
            if sw_pin.value() == False and not button_down:
                previous_time = current_time
                button_down = True
                time.sleep_ms(3)
                break
            
            if sw_pin.value() and button_down:
                button_down = False
                time.sleep_ms(3)
            if elapsed_time >= 30000:  # 1 saniye geçti
                previous_time = current_time  # Geçen zamanı sıfırla
                break
        except Exception as e:
            print(e)
    if not cond:
        time.sleep_ms(3000)

"""--------------------------------------------------------------------------------"""
"""-------------------------------ABOUT END----------------------------------------"""
"""--------------------------------------------------------------------------------"""
def read_uids():
    with open("card_lib.dat") as f:
        lines = f.readlines()
    uids = []
    for line in lines:
        uid = line.strip("\n").replace('[', '').replace(']', '').split(', ')
        uid = [int(x, 0) for x in uid]  # Hexadecimal olarak okuma
        uids.append(uid)
    return uids

def write_uids(uids):
    with open("card_lib.dat", "w") as f:
        for uid in uids:
            f.write("[%s]\n" % (', '.join(hex(x) for x in uid)))

def card_generator(cond):
    tft.fill(st7789.BLACK)
    center_text(0, lang["adding_card"], font, st7789.color565(0, 255, 0))
    center_text(50, lang["card"], font, st7789.color565(0, 255, 0))
    center_text(64, lang["scan"], font, st7789.color565(0, 255, 0))
    from mfrc522 import MFRC522
    import utime
    reader = MFRC522(spi_id=0, sck=2, miso=4, mosi=3, cs=1, rst=0)
    try:
        while True:
            reader.init()
            (stat, tag_type) = reader.request(reader.REQIDL)
            if stat == reader.OK:
                (stat, uid) = reader.SelectTagSN()
                if stat == reader.OK:
                    try:
                        uids = read_uids()
                    except Exception as e:
                        uids = []
                        print(e)
                    if cond == 'add':
                        print(uids)
                        if uid in uids:
                            center_text(50, lang["card"], font, color565(0, 255, 0))
                            center_text(64, lang["already_registered"], font, st7789.color565(180, 0, 0))
                            config['setup']=True
                            time.sleep_ms(1000)
                        else:
                            print("liste: ",uids,"okunan uid: ",uid)
                            uids.append(uid)
                            print("yeni liste: ",uids)
                            write_uids(uids)
                            center_text(50, lang["card"], font, st7789.color565(0, 255, 0))
                            center_text(64, lang["registered"], font, st7789.color565(0, 255, 0))
                            config['setup']=True
                            time.sleep_ms(1000)
                    elif cond == 'delete':
                        if uid in uids:
                            print("liste: ",uids,"okunan uid: ",uid)
                            uids.remove(uid)
                            print("yeni liste: ",uids)
                            write_uids(uids)
                            center_text(50, lang["card"], font, st7789.color565(0, 255, 0))
                            center_text(64, lang["deleted"], font, st7789.color565(0, 255, 0))
                            del uids
                            time.sleep_ms(1000)
                        elif uid not in uids:
                            center_text(50, lang["card"], font, st7789.color565(0, 255, 0))
                            center_text(64, lang["not_in_list"], font, st7789.color565(0, 0, 255))
                            time.sleep_ms(1000)
                    PreviousCard = uid
                    break
                else:
                    pass
            else:
                PreviousCard = [0]
            time.sleep_ms(50)

    except KeyboardInterrupt:
        pass
"""--------------------------------------------------------------------------------"""
"""--------------------------------SETTINGS----------------------------------------"""
"""--------------------------------------------------------------------------------"""


def settings_menu():
    global button_down, blynk, previous_value, highlight, shift
    box = ['', config['thermistor_offset'],config['termistor_type'],
           '', '',config["language"], '']
    file_list = [
        lang["back"],
        lang["thermistor_offset"],
        lang["termistor_type"],
        lang["adding_card"],
        lang["deleting_card"],
        lang["language"],
        lang["reset"]
        ]
    if len(file_list) >= 6:
        total_lines = 6
    else:
        total_lines = len(file_list)

    def show_menu(menu, box):
        """ Shows the menu on the screen"""
        # bring in the global variables
        global line, highlight, shift, list_length
        # menu variables
        item = 1
        boxitem = 2
        line = 1
        line_height = 40
        list_length = len(menu)
        short_list = menu[shift:shift + total_lines]
        box_list_length = len(box)
        sort_box_list = box[shift:shift + total_lines]
        tft.fill(st7789.BLACK) 
        for item, boxitem in zip(short_list, sort_box_list):
            if highlight == line:
                tft.text(font,'>',0,(line - 1) * line_height + 5,st7789.CYAN)  # menu item pointer
                tft.text(font,item,25,(line - 1) * line_height + 5,st7789.CYAN)  # menu item text
                tft.text(font,str(boxitem),170,(line - 1) * line_height + 5,st7789.CYAN)  # menu item's values
            else:
                tft.text(font,item,10,(line - 1) * line_height + 5,st7789.WHITE)  # rest of menu items
                tft.text(font,str(boxitem),170,(line - 1) * line_height + 5, st7789.WHITE)  # rest of menu items's values
            line += 1

    def factory_settings():
        try:
            del config
            with open('config_backup.json', 'r') as f:  # read the json file
                config = json.load(f)
            os.remove('wifi.dat')
            os.remove('card_lib.dat')
            write_config()
            reset_settings=True
            time.sleep(1)
        except BaseException:
            tft.fill(st7789.BLACK) 
            center_text(
                0, lang["reset_error"], font, st7789.color565(
                    72, 222, 105))  # call for center the text
        if reset_settings:
            machine.reset()


    def launch(filename):
        if filename == lang["thermistor_offset"]:
            config['thermistor_offset']=set_value(config['thermistor_offset'], 0.1)
            box[1]=config['thermistor_offset']
        elif filename == lang["reset"]:
            factory_settings()
        elif filename == lang["adding_card"]:
            card_generator('add')
        elif filename == lang["deleting_card"]:
            card_generator('delete')
        elif filename == lang["language"]:
            language_menu()
        elif filename==lang["termistor_type"]:
            if config['termistor_type']=='ntc':
                config['termistor_type']='ptc'
            elif config['termistor_type']=='ptc':
                config['termistor_type']='ntc'
            box[2]=config['termistor_type']
            write_config()
    show_menu(file_list, box)
    previous_time = time.ticks_ms()
    msg_prev_time = time.ticks_ms()
    while True:
        try:
            gc.collect()
            current_time = time.ticks_ms()
            elapsed_time = current_time - previous_time
            msg_runout_time = current_time - msg_prev_time
            # Check for encoder rotated
            if previous_value != dt_pin.value():
                previous_time = current_time
                if dt_pin.value() == False:
                    if clk_pin.value() == False:
                        if highlight > 1:
                            highlight -= 1
                        else:
                            if shift > 0:
                                shift -= 1
                    else:
                        if highlight < total_lines:
                            highlight += 1
                        else:
                            if shift + total_lines < list_length:
                                shift += 1
                    show_menu(file_list, box)
                previous_value = dt_pin.value()
            time.sleep_ms(1)

            if sw_pin.value() == False and not button_down:
                button_down = True
                time.sleep_ms(3)
                if file_list[(highlight - 1) + shift]==lang["back"]:
                    break
                else:
                    launch(file_list[(highlight - 1) + shift])
                show_menu(file_list, box)
                previous_time = current_time
            if sw_pin.value() and button_down:
                button_down = False
                time.sleep_ms(3)
            if elapsed_time >= 1000:  # 1 saniye geçti
                previous_time = current_time  # Geçen zamanı sıfırla
                
            if msg_runout_time >= 30000:  # 1 saniye geçti
                msg_prev_time = current_time
                break
        except Exception as e:
            print(e)
"""--------------------------------------------------------------------------------"""
"""-------------------------------SETTINGS END-------------------------------------"""
"""--------------------------------------------------------------------------------"""

"""--------------------------------------------------------------------------------"""
"""----------------------------------WEIGHT----------------------------------------"""
"""--------------------------------------------------------------------------------"""


def weight_menu():
    global button_down, temp_treshould_state,previous_value, highlight, shift,steinhart_y,weight_y,liter_y
    box = [
        '',
        '',
        '',
        '',
        config['weight']['scale_factor'],
        config['weight']['self_weight'],
        config['weight']['weight_1'],
        config['weight']['weight_2']]
    file_list = [
        lang["back"],
        config['weight']['weightcond'],
        lang["tare"],
        lang["calibration"],
        lang["scale_factor_set"],
        lang["tank_weight"],
        lang["weight1"],
        lang["weight2"]]
    if len(file_list) >= 6:
        total_lines = 6
    else:
        total_lines = len(file_list)

    def show_menu(menu, box):
        """ Shows the menu on the screen"""
        # bring in the global variables
        global line, highlight, shift, list_length
        # menu variables
        item = 1
        line = 1
        line_height = 40
        list_length = len(menu)
        short_list = menu[shift:shift + total_lines]
        box_list_length = len(box)
        sort_box_list = box[shift:shift + total_lines]
        tft.fill(st7789.BLACK) 
        for item, boxitem in zip(short_list, sort_box_list):
            if highlight == line:
                tft.text(font,'>',0,(line - 1) * line_height + 5,st7789.CYAN)  # menu item pointer
                if item == "AKTIF":
                    tft.text(font,item,25,(line - 1) * line_height + 5,st7789.GREEN)  # menu item text
                elif item == "PASIF":
                    tft.text(font,item,25,(line - 1) * line_height + 5,st7789.RED)  # menu item text
                else:
                    tft.text(font,item,25,(line - 1) * line_height + 5,st7789.CYAN)  # menu item text
                tft.text(font,str(boxitem),175,(line - 1) * line_height + 5,st7789.CYAN)  # menu item's values
            else:
                if item == "AKTIF":
                    tft.text(font,item,10,(line - 1) * line_height + 5,st7789.GREEN)  # menu item text
                elif item == "PASIF":
                    tft.text(font,item,10,(line - 1) * line_height + 5,st7789.RED)  # menu item text
                else:
                    tft.text(font,item,10,(line - 1) * line_height + 5,st7789.WHITE)  # menu item text
                tft.text(font,str(boxitem),150,(line - 1) * line_height + 5,st7789.WHITE)  # rest of menu items's values
            line += 1

    def calibrate_weight_sensor():
        global button_down
        tft.fill(st7789.BLACK) 
        center_text(80, f"{config['weight']['weight_1']}kg {lang['of_weight']}", font, st7789.color565(0, 255, 0))
        center_text(110, lang["put"], font, st7789.color565(0, 255, 0))
        measurement = False
        while measurement != True:
            if sw_pin.value() == False and not button_down:
                button_down = True

                raw_values1 = []
                for i in range(5):
                    raw_values1.append(hx711.read())
                raw_value1 = sum(raw_values1) / len(raw_values1)
                measurement = True
                sleep(1)
            if sw_pin.value() and button_down:
                button_down = False
        sleep(0.01)
        tft.fill(st7789.BLACK) 
        center_text(80, f"{config['weight']['weight_1']}kg {lang['of_weight']}", font, st7789.color565(0, 255, 0))
        center_text(110, lang["take"], font, st7789.color565(0, 255, 0))
        sleep(2)
        tft.fill(st7789.BLACK) 
        center_text(80, f"{config['weight']['weight_2']}kg {lang['of_weight']}", font, st7789.color565(0, 255, 0))
        center_text(110, lang["put"], font, st7789.color565(0, 255, 0))
        measurement = False
        while measurement != True:
            if sw_pin.value() == False and not button_down:
                button_down = True
                raw_values2 = []
                for i in range(5):
                    raw_values2.append(hx711.read())
                raw_value2 = sum(raw_values2) / len(raw_values2)
                measurement = True
                sleep(1)
            if sw_pin.value() and button_down:
                button_down = False
        sleep(0.01)
        try:
            # scale factor  ortalamasi alinir
            scale_factor = round((raw_value1 - raw_value2) / (float(onfig['weight']['weight_1']) - float(config['weight']['weight_2'])))
            config['weight']['scale_factor'] = scale_factor
            tft.fill(st7789.BLACK) 
            write_config()
            center_text(80, lang["calibration"], font, st7789.color565(0, 255, 0))
            center_text(110, lang["ok"], font, st7789.color565(0, 255, 0))
            sleep(2)
        except BaseException:
            tft.fill(st7789.BLACK) 
            center_text(80, lang["calibration"], font, st7789.color565(0, 255, 0))
            center_text(110, lang["error"], font, st7789.color565(0, 255, 0))
            sleep(2)

    def tare():
        tft.fill(st7789.BLACK) 
        center_text(100, lang["tare_process"], font, st7789.color565(0, 255, 0))
        tares = []
        for i in range(5):
            tares.append(hx711.read())
        config['weight']['self_weight'] = round(((sum(tares) / len(tares)) / config['weight']['scale_factor']),1)  # okunan raw values degerlerinin ortalamasi alinir
        write_config()
        time.sleep_ms(1000)
        tft.fill(st7789.BLACK) 
        center_text(100, lang["tare_ok"], font, st7789.color565(0, 255, 0))
        time.sleep_ms(1000)

    def launch(filename):
        if filename == file_list[1]:
            if config['weight']['weightcond'] == "AKTIF":
                config['weight']['weightcond'] = "PASIF"
            elif config['weight']['weightcond'] == "PASIF":
                config['weight']['weightcond'] = "AKTIF"
            write_config()
            file_list[1] = config['weight']['weightcond']
        elif filename == lang["scale_factor_set"]:
            config['weight']['scale_factor']=set_value(config['weight']['scale_factor'], 1)
            box[4]=config['weight']['scale_factor']
        elif filename == lang["calibration"]:
            calibrate_weight_sensor()
        elif filename == lang["tare"]:
            tare()
        elif filename == lang["tank_weight"]:
            config['weight']['self_weight']= set_value(config['weight']['self_weight'], 1)
            box[5]=config['weight']['self_weight']
        elif filename ==lang["weight1"]:
            config['weight']['weight_1']=set_value(config['weight']['weight_1'],1)
            box[6]=config['weight']['weight_1']
        elif filename ==lang["weight2"]:
            config['weight']['weight_2']=set_value(config['weight']['weight_2'],1)
            box[7]=config['weight']['weight_2']
    show_menu(file_list, box)
    screen_timeout_in = time.ticks_ms()
    while True:
        try:
            gc.collect()
            current_time = time.ticks_ms()
            screen_timeout = current_time - screen_timeout_in  # Geçen süreyi kontrol et
            if previous_value != dt_pin.value():
                screen_timeout_in = current_time
                if dt_pin.value() == False:
                    # Turned Left
                    if clk_pin.value() == False:
                        if highlight > 1:
                            highlight -= 1
                        else:
                            if shift > 0:
                                shift -= 1
                    else:
                        if highlight < total_lines:
                            highlight += 1
                        else:
                            if shift + total_lines < list_length:
                                shift += 1
                    show_menu(file_list, box)
                previous_value = dt_pin.value()
            time.sleep_ms(1)
            if sw_pin.value() == False and not button_down:
                screen_timeout_in = current_time
                button_down = True
                if file_list[(highlight - 1) + shift]==lang["back"]:
                    break
                else:
                    launch(file_list[(highlight - 1) + shift])
                show_menu(file_list, box)
                
            if sw_pin.value() and button_down:
                button_down = False
                time.sleep_ms(3)
            if screen_timeout >= 30000:  # 1 saniye geçti
                screen_timeout_in = current_time  # Geçen zamanı sıfırla
                break
        except Exception as e:
            print("while(): ", e)
"""--------------------------------------------------------------------------------"""
"""--------------------------------WEIGHT END--------------------------------------"""
"""--------------------------------------------------------------------------------"""
"""--------------------------------------------------------------------------------"""
"""----------------------------------MIXER-----------------------------------------"""
"""--------------------------------------------------------------------------------"""
def mixer_menu():
    global button_down, temp_treshould_state, previous_value, highlight, shift
    box = ['', '', config['mixer']['mixerwork'], config['mixer']['mixerwait']]
    file_list = [
        lang["back"],
        config['mixer']['mixercond'],
        lang["work_time"],
        lang["wait_time"]]
    if len(file_list) >= 6:
        total_lines = 6
    else:
        total_lines = len(file_list)

    def show_menu(menu, box):
        """ Shows the menu on the screen"""
        # bring in the global variables
        global line, highlight, shift, list_length
        # menu variables
        item = 1
        boxitem = 2
        line = 1
        line_height = 40
        list_length = len(menu)
        short_list = menu[shift:shift + total_lines]
        box_list_length = len(box)
        sort_box_list = box[shift:shift + total_lines]
        tft.fill(st7789.BLACK) 
        for item, boxitem in zip(short_list, sort_box_list):
            if highlight == line:
                tft.text(font,'>',0,(line - 1) * line_height + 5,st7789.CYAN)  # menu item pointer
                if item == "AKTIF":
                    tft.text(font,item,25,(line - 1) * line_height + 5,st7789.GREEN)  # menu item text
                elif item == "PASIF":
                    tft.text(font,item,25,(line - 1) * line_height + 5,st7789.RED)  # menu item text
                else:
                    tft.text(font,item,25,(line - 1) * line_height + 5,st7789.CYAN)  # menu item text
                tft.text(font,str(boxitem),170,(line - 1) * line_height + 5,st7789.CYAN)  # menu item's values
            else:
                if item == "AKTIF":
                    tft.text(font,item,10,(line - 1) * line_height + 5,st7789.GREEN)  # menu item text
                elif item == "PASIF":
                    tft.text(font,item,10,(line - 1) * line_height + 5,st7789.RED)  # menu item text
                else:
                    tft.text(font,item,10,(line - 1) * line_height + 5,st7789.WHITE)  # menu item text
                tft.text(font,str(boxitem),170,(line - 1) * line_height + 5,st7789.WHITE)  # rest of menu items's values
            line += 1

    def launch(filename):
        if filename == file_list[1]:
            if config['mixer']['mixercond'] == "AKTIF":
                config['mixer']['mixercond'] = "PASIF"
                mixer_pin.value(0)
            elif config['mixer']['mixercond'] == "PASIF":
                config['mixer']['mixercond'] = "AKTIF"
                mixer_pin.value(1)
            write_config()
            file_list[1] = config['mixer']['mixercond']
        elif filename == lang["work_time"]:
            config['mixer']['mixerwork']= set_value(config['mixer']['mixerwork'], 1)
            box[2]=config['mixer']['mixerwork']
        elif filename == lang["wait_time"]:
            config['mixer']['mixerwait']=set_value(config['mixer']['mixerwait'], 1)
            box[3]=config['mixer']['mixerwait']
    show_menu(file_list, box)

    previous_time = time.ticks_ms()
    screen_timeout_in = time.ticks_ms()
    while True:
        try:
            gc.collect()
            current_time = time.ticks_ms()
            elapsed_time = current_time - previous_time  # Geçen süreyi kontrol et
            screen_timeout = current_time - screen_timeout_in  # Geçen süreyi kontrol et
            if elapsed_time >= 1000:  # 1 saniye geçti
                previous_time = current_time  # Geçen zamanı sıfırla
            # Check for encoder rotated
            if previous_value != dt_pin.value():
                screen_timeout_in = current_time
                if dt_pin.value() == False:
                    # Turned Left
                    if clk_pin.value() == False:
                        if highlight > 1:
                            highlight -= 1
                        else:
                            if shift > 0:
                                shift -= 1
                    # Turned Right
                    else:
                        if highlight < total_lines:
                            highlight += 1
                        else:
                            if shift + total_lines < list_length:
                                shift += 1
                    show_menu(file_list, box)
                previous_value = dt_pin.value()
            time.sleep_ms(1)
            if sw_pin.value() == False and not button_down:
                screen_timeout_in = current_time
                button_down = True
                if file_list[(highlight - 1) + shift]==lang["back"]:
                    break
                else:
                    launch(file_list[(highlight - 1) + shift])
                show_menu(file_list, box)
            if sw_pin.value() and button_down:
                button_down = False
                time.sleep_ms(1)
            if screen_timeout >= 30000:  # 1 saniye geçti
                screen_timeout_in = current_time  # Geçen zamanı sıfırla
                break
        except Exception as e:
            print("while(): ", e)

"""--------------------------------------------------------------------------------"""
"""---------------------------------MIXER END--------------------------------------"""
"""--------------------------------------------------------------------------------"""
"""--------------------------------------------------------------------------------"""
"""---------------------------------LANGUAGE---------------------------------------"""
"""--------------------------------------------------------------------------------"""

def language_menu():
    global button_down, previous_value, highlight, shift
    line = 1
    highlight = 1
    shift = 0
    file_list = [
        lang["back"],
        "TURKCE",
        "ENGLISH",
        ]
    if len(file_list) >= 6:
        total_lines = 6
    else:
        total_lines = len(file_list)

    def show_menu(menu):
        """ Shows the menu on the screen"""
        # bring in the global variables
        global line, highlight, shift, list_length
        item = 1
        line = 1
        line_height = 40
        list_length = len(menu)
        short_list = menu[shift:shift + total_lines]
        tft.fill(st7789.BLACK)
        for item in short_list:
            if highlight == line:
                tft.text(font,'>',0,(line - 1) * line_height + 5,st7789.CYAN)  # menu item pointer
                tft.text(font,item,25,(line - 1) * line_height + 5,st7789.CYAN)  # menu item text
            else:
                tft.text(font,item,10,(line - 1) * line_height + 5,st7789.WHITE)  # menu item text
            line += 1

    def launch(filename):
        if filename=='TURKCE':
            config["language"]='tr'
        elif filename=='ENGLISH':
            config["language"]='en'
        write_config()
        try:
            open_language_file(config["language"],change=True)
        except Exception as s:
            print(s)
        
    show_menu(file_list)
    previous_time = time.ticks_ms()
    screen_timeout_in = time.ticks_ms()
    while True:
        try:
            gc.collect()
            current_time = time.ticks_ms()
            screen_timeout = current_time - screen_timeout_in  # Geçen süreyi kontrol et
            # Check for encoder rotated
            if previous_value != dt_pin.value():
                screen_timeout_in = current_time
                if dt_pin.value() == False:
                    # Turned Left
                    if clk_pin.value() == False:
                        if highlight > 1:
                            highlight -= 1
                        else:
                            if shift > 0:
                                shift -= 1
                    # Turned Right
                    else:
                        if highlight < total_lines:
                            highlight += 1
                        else:
                            if shift + total_lines < list_length:
                                shift += 1
                    show_menu(file_list)
                previous_value = dt_pin.value()
            time.sleep_ms(1)

            if sw_pin.value() == False and not button_down:
                button_down = True
                if file_list[(highlight - 1) + shift]==lang["back"]:
                    break
                else:
                    launch(file_list[(highlight - 1) + shift])
                tft.fill(st7789.BLACK)
                draw_message(lang["please_wait"])
                screen_timeout_in = current_time
                time.sleep_ms(3)

            if sw_pin.value() and button_down:
                button_down = False
                time.sleep_ms(3)
            if screen_timeout >= 30000:  # 1 saniye geçti
                screen_timeout_in = current_time  # Geçen zamanı sıfırla
                break
        except OSError:
            time.sleep_ms(1000)

"""--------------------------------------------------------------------------------"""
"""---------------------------------LANG END --------------------------------------"""
"""--------------------------------------------------------------------------------"""
"""--------------------------------------------------------------------------------"""
"""----------------------------------COOLER ---------------------------------------"""
"""--------------------------------------------------------------------------------"""

def cooler_menu():
    global button_down, temp_treshould_state, previous_value, highlight, shift
    box = [
        '',
        '',
        config['cooler']['tempset'],
        config['cooler']['temptolerance']]
    file_list = [
        lang["back"],
        config['cooler']['coolercond'],
        lang["constant_tem"],
        lang["tolerance"]]
    if len(file_list) >= 6:
        total_lines = 6
    else:
        total_lines = len(file_list)

    def show_menu(menu, box):
        """ Shows the menu on the screen"""
        # bring in the global variables
        global line, highlight, shift, list_length
        item = 1
        boxitem = 1
        line = 1
        line_height = 40
        list_length = len(menu)
        short_list = menu[shift:shift + total_lines]
        box_list_length = len(box)
        sort_box_list = box[shift:shift + total_lines]
        tft.fill(st7789.BLACK) 
        for item, boxitem in zip(short_list, sort_box_list):
            if highlight == line:
                tft.text(font,'>',0,(line - 1) * line_height + 5,st7789.CYAN)  # menu item pointer
                if item == "AKTIF":
                    tft.text(font,item,25,(line - 1) * line_height + 5,st7789.GREEN)  # menu item text
                elif item == "PASIF":
                    tft.text(font,item,25,(line - 1) * line_height + 5,st7789.RED)  # menu item text
                else:
                    tft.text(font,item,25,(line - 1) * line_height + 5,st7789.CYAN)  # menu item text
                tft.text(font,str(boxitem),170,(line - 1) * line_height + 5,st7789.CYAN)  # menu item's values
            else:
                if item == "AKTIF":
                    tft.text(font,item,10,(line - 1) * line_height + 5,st7789.GREEN)  # menu item text
                elif item == "PASIF":
                    tft.text(font,item,10,(line - 1) * line_height + 5,st7789.RED)  # menu item text
                else:
                    tft.text(font,item,10,(line - 1) * line_height + 5,st7789.WHITE)  # menu item text
                tft.text(font,str(boxitem),170,(line - 1) * line_height + 5,st7789.WHITE)  # rest of menu items's values
            line += 1

    def launch(filename):
        if filename == file_list[1]:
            if config['cooler']['coolercond'] == "AKTIF":
                config['cooler']['coolercond'] = "PASIF"
                cooler_pin.value(0)
            elif config['cooler']['coolercond'] == "PASIF":
                config['cooler']['coolercond'] = "AKTIF"
                cooler_pin.value(1)
            write_config()
            file_list[1] = config['cooler']['coolercond']
        elif filename == lang["constant_tem"]:
            config['cooler']['tempset']=set_value(config['cooler']['tempset'], 0.1)
            box[2]=config['cooler']['tempset']
        elif filename == lang["tolerance"]:
            config['cooler']['temptolerance']= set_value(config['cooler']['temptolerance'], 0.1)
            box[5]=config['cooler']['temptolerance']

    show_menu(file_list, box)
    screen_timeout_in = time.ticks_ms()

    while True:
        try:
            gc.collect()
            current_time = time.ticks_ms()
            screen_timeout = current_time - screen_timeout_in  # Geçen süreyi kontrol et
            # Check for encoder rotated
            if previous_value != dt_pin.value():
                screen_timeout_in = current_time
                if dt_pin.value() == False:
                    # Turned Left
                    if clk_pin.value() == False:
                        if highlight > 1:
                            highlight -= 1
                        else:
                            if shift > 0:
                                shift -= 1
                    # Turned Right
                    else:
                        if highlight < total_lines:
                            highlight += 1
                        else:
                            if shift + total_lines < list_length:
                                shift += 1
                    show_menu(file_list, box)
                previous_value = dt_pin.value()
            time.sleep_ms(1)

            if sw_pin.value() == False and not button_down:
                button_down = True
                if file_list[(highlight - 1) + shift]==lang["back"]:
                    break
                else:
                    launch(file_list[(highlight - 1) + shift])
                show_menu(file_list, box)
                screen_timeout_in = current_time
                time.sleep_ms(3)

            if sw_pin.value() and button_down:
                button_down = False
                time.sleep_ms(3)
            if screen_timeout >= 30000:  # 1 saniye geçti
                screen_timeout_in = current_time  # Geçen zamanı sıfırla
                break
        except OSError:
            time.sleep_ms(1000)

"""--------------------------------------------------------------------------------"""
"""--------------------------------COOLER END--------------------------------------"""
"""--------------------------------------------------------------------------------"""

"""--------------------------------------------------------------------------------"""
"""---------------------------------MAIN MENU -------------------------------------"""
"""--------------------------------------------------------------------------------"""


def mainmenu():
    menu = [
        (lang["back"], ''),
        (lang["cooler"], 'cooler_menu()'),
        (lang["mixer"], 'mixer_menu()'),
        (lang["weight"], 'weight_menu()'),
        (lang["settings"], 'settings_menu()'),
        (lang["about"], 'about_page(True)')
    ]

    width = 240
    line = 1
    highlight = 1
    shift = 0
    list_length = 0
    if len(menu) >= 6:
        total_lines = 6
    else:
        total_lines = len(menu)

    previous_value = True
    button_down = False

    def show_menu(menu):
        """ Shows the menu on the screen"""
        # bring in the global variables
        global line, list_length
        # menu variables
        item = 1
        line = 1
        line_height = 40
        list_length = len(menu)
        short_list = menu[shift:shift + total_lines]
        tft.fill(st7789.BLACK) 
        for item, ifilename in short_list:
            if highlight == line:
                tft.text(font,'>',0,(line - 1) * line_height + 5,st7789.GREEN)
                tft.text(font,item,25,(line - 1) * line_height + 5,st7789.GREEN)
            else:
                tft.text(font,item,10,(line - 1) * line_height + 5,st7789.color565(255,255,255))
            line += 1
        return ifilename

    def launch(filename):
        eval(filename[1])
    show_menu(menu)
    previous_time = time.ticks_ms()
    while True:
        try:
            gc.collect()
            current_time = time.ticks_ms()
            elapsed_time = current_time - previous_time
            # Check for encoder rotated
            if previous_value != dt_pin.value():
                previous_time = current_time
                if dt_pin.value() == False:
                    # Turned Left
                    if clk_pin.value() == False:
                        if highlight > 1:
                            highlight -= 1
                        else:
                            if shift > 0:
                                shift -= 1
                    # Turned Right
                    else:
                        if highlight < total_lines:
                            highlight += 1
                        else:
                            if shift + total_lines < list_length:
                                shift += 1
                    show_menu(menu)
                previous_value = dt_pin.value()
            if sw_pin.value() == False and not button_down:
                button_down = True
                if menu[(highlight - 1) + shift][0]==lang["back"]:
                    home()  
                    break
                launch(menu[(highlight - 1) + shift])
                show_menu(menu)
                time.sleep_ms(3)
            if sw_pin.value() and button_down:
                button_down = False
                time.sleep_ms(3)
            if elapsed_time >= 30000:  # 1 saniye geçti
                previous_time = current_time  # Geçen zamanı sıfırla
                home()
                break
        except Exception as e:
            print(e)


"""--------------------------------------------------------------------------------"""
"""------------------------------MAIN MENU END-------------------------------------"""
"""--------------------------------------------------------------------------------"""


def main():
    home()
    global button_down, steinhart, temp_treshould_state,access
    previous_time = time.ticks_ms()
    msg_prev_time = time.ticks_ms()
    while True:
        try:
            current_time = time.ticks_ms()
            elapsed_time = current_time - previous_time
            msg_runout_time = current_time - msg_prev_time
            # Geçen süreyi kontrol et
            if elapsed_time >= 1000:  # 1 saniye geçti
                gc.collect()
                temperature()
                weight()
                previous_time = current_time  # Geçen zamanı sıfırla
            if msg_runout_time >= 30000:
                tft.fill_rect(0, 225, 240, 240, st7789.BLACK)
                text = " "
                msg_prev_time = current_time
            if sw_pin.value() == False and not button_down:
                button_down = True
                sleep(0.2)
                rfidread()
            if sw_pin.value() and button_down:
                button_down = False

            if steinhart >= config['cooler']['tempset'] + \
                    config['cooler']['temptolerance'] and config['cooler']['coolercond'] == 'AKTIF' and config['mixer']['mixercond'] == 'AKTIF':
                cooler_pin.value(1)
                mixer_pin.value(1)
                if not temp_treshould_state:
                    home()
                temp_treshould_state = True
            if steinhart < config['cooler']['tempset'] and config['mixer']['mixercond'] == 'AKTIF':
                temp_treshould_state == False
                mixer_toogle(current_time)
            if steinhart >= config['cooler']['tempset'] and temp_treshould_state == False and config['mixer']['mixercond'] == 'AKTIF':
                mixer_toogle(current_time)
            sleep(0.01)
        except Exception as e:
            home()
            print("main loop error: ", e)
            draw_message("HATA [M]")


if __name__ == "__main__":
    about_page(False)
    if config['setup']!=True or not 'card_lib.dat' in os.listdir():
        tft.fill(st7789.BLACK)
        center_text(50, lang["first"], font, st7789.color565(0, 255, 0))
        center_text(64, lang["setup"], font, st7789.color565(0, 255, 0))
        time.sleep(2)
        center_text(50, lang["card"], font, st7789.color565(0, 255, 0))
        center_text(64, lang["identify"], font, st7789.color565(0, 255, 0))
        time.sleep(2)
        card_generator('add')
    main()
