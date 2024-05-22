
import time
import os
import board
import displayio
from digitalio import DigitalInOut, Direction, Pull
from adafruit_matrixportal.matrix import Matrix
from adafruit_debouncer import Debouncer
import adafruit_lis3dh
from audiocore import WaveFile

# --- Button setup ---
pin_down = DigitalInOut(board.BUTTON_DOWN)
pin_down.switch_to_input(pull=Pull.UP)
button_down = Debouncer(pin_down)
pin_up = DigitalInOut(board.BUTTON_UP)
pin_up.switch_to_input(pull=Pull.UP)
button_up = Debouncer(pin_up)



try:
    from audioio import AudioOut, WaveFile
except ImportError:
    try:
        from audiopwmio import PWMAudioOut as AudioOut
    except ImportError:
        pass  # not always supported by every board!

class TonyAudio:

    def __init__(self ):
        self.audio_output = None
        # this mutes the audio by setting it the pin to low.
        self.pin_output = DigitalInOut(board.A0)
        self.pin_output.direction = Direction.OUTPUT
        self.pin_output.value = False  # Set pin to low

    
    def __clear_all__(self):
        if self.pin_output is not None:
            self.pin_output.deinit()
            self.pin_output = None
        if self.audio_output is not None:
            self.audio_output.deinit()
            self.audio_output = None
        

    def __init_audio_output__(self):
        # first clear everything out
        self.__clear_all__()
        # now set up the audio output to the A0 pin
        self.audio_output = AudioOut(board.A0)
  
    def play(self, filename):
        global is_muted
        if(self.audio_output is not None and self.audio_output.playing):
            return 
        wave_file = open(filename, "rb")
        wave = WaveFile(wave_file)
        if not is_muted:
            self.__init_audio_output__()
            self.audio_output.play(wave)
    
    def stop(self):
        if self.audio_output is not None:
            self.audio_output.stop()
            self.audio_output.deinit()
            self.audio_output = None

            self.pin_output = DigitalInOut(board.A0)
            self.pin_output.direction = Direction.OUTPUT
            self.pin_output.value = False  # Set pin to lowz


# Create an instance of the TonyAudio class
tony_audio = TonyAudio()


def handle_tudum():
    global current_frame, current_loop, tony_audio, lis3dh
    tudum_delay_interval = 0.08
    tudum_last_time = time.monotonic()
    
    #load up the spritesheet
    load_image("tudum.bmp")

    #keep going as long as we are not done with the loop of frames
    while current_loop < 1:
        if tony_audio.audio_output and not tony_audio.audio_output.playing:
            # if for whatever reason the audio isn't playing but hte object is available, stop it (clearing the baffles)
            tony_audio.stop()

        # slicing the time into 0.1 second intervals (the framerate!)
        current_time_a = time.monotonic()
        if current_time_a - tudum_last_time >= tudum_delay_interval:

            '''
                This is a "white glove" approach to handling the frames and playing the music for the "Tudum" sound... lol

                When writing to the LCD display, this microcontroller introduces a bunch of noise,
                and the audio sounded shite

                So the first 5 frames of the Netflix N logo animate,
                then we play the "Tudum" sound since the N is fully displayed.
                We wait until after the sound is done
                then we finish the remaining frames of the animation
            '''
            if current_frame < 5:
                advance_frame()
            elif current_frame == 6:
                tony_audio.play("wav/tudum.wav")
                while tony_audio.audio_output is not None and tony_audio.audio_output.playing:
                    check_mute()
                    # pass
                advance_frame()
            else:
                advance_frame()
            
          
             # Reset the last_time to the current time
            tudum_last_time = current_time_a
    load_image()


    
    

# --- LIS3DH/TAP DETECTION SETUP ---
# PyGamer or MatrixPortal I2C Setup:
i2c = board.I2C()  # uses board.SCL and board.SDA
lis3dh = adafruit_lis3dh.LIS3DH_I2C(i2c, address=0x19)

# Set range of accelerometer (can be RANGE_2_G, RANGE_4_G, RANGE_8_G or RANGE_16_G).
lis3dh.range = adafruit_lis3dh.RANGE_2_G
lis3dh.set_tap(1, 80)

# vars for tap detection
last_tap_time = 0
has_single_tapped = False

def has_double_tap():
    global has_single_tapped, last_tap_time, current_time

    double_tap_threshold = 0.5  # Time in seconds within which a second tap should be registered as a double-tap

    if lis3dh.tapped:
        if has_single_tapped and (current_time - last_tap_time) < double_tap_threshold:
            # print("Double tapped!")
            has_single_tapped = False  # Reset the tap state
            return True
        else:
            # Record the time of this tap
            has_single_tapped = True
            last_tap_time = current_time
            return False

    # Reset single tap if time threshold exceeds without a second tap
    if has_single_tapped and (current_time - last_tap_time) >= double_tap_threshold:
        has_single_tapped = False

    # No tap or valid double tap within the allowed interval
    return False



# IMAGE SETUP

SPRITESHEET_FOLDER = "/bmps"
DEFAULT_FRAME_DURATION = 0.1  # 100ms
AUTO_ADVANCE_LOOPS = 3
# this is used to have bespoke framerates per spritesheet.
FRAME_DURATION_OVERRIDES = {
    # "my_bmp.bmp": 0.001,
}

# --- Display setup ---
matrix = Matrix(bit_depth=3, width=64, height=32)
sprite_group = displayio.Group()
matrix.display.root_group = sprite_group


auto_advance = True

file_list = sorted(
    [
        f
        for f in os.listdir(SPRITESHEET_FOLDER)
        if (f.endswith(".bmp") and not f.startswith(".") and not f.startswith("tudum"))
    ]
)

if len(file_list) == 0:
    raise RuntimeError("No images found")

current_image = None
current_frame = 0
current_loop = 0
frame_count = 0
frame_duration = DEFAULT_FRAME_DURATION


# tudum_bitmap = displayio.OnDiskBitmap(open('bmps/tudum.bmp', "rb"))

def load_image(specific_image=None):
    global tudum_bitmap

    """
    Load an image as a sprite
    """
    # pylint: disable=global-statement
    global current_frame, current_loop, frame_count, frame_duration
    while sprite_group:
        sprite_group.pop()

    if specific_image:
        filename = SPRITESHEET_FOLDER + "/" + specific_image
    else:
        filename = SPRITESHEET_FOLDER + "/" + file_list[current_image]

    # CircuitPython 6 & 7 compatible
    if specific_image == "tudum.bmp":
        # bitmap = tudum_bitmap
        bitmap = displayio.OnDiskBitmap(open('bmps/tudum.bmp', "rb"))
    else:
        bitmap = displayio.OnDiskBitmap(open(filename, "rb"))
    
    sprite = displayio.TileGrid(
        bitmap,
        pixel_shader=getattr(bitmap, 'pixel_shader', displayio.ColorConverter()),
        tile_width=bitmap.width,
        tile_height=matrix.display.height,
    )


    sprite_group.append(sprite)

    current_frame = 0
    current_loop = 0
    frame_count = int(bitmap.height / matrix.display.height)
    frame_duration = DEFAULT_FRAME_DURATION
    if file_list[current_image] in FRAME_DURATION_OVERRIDES:
        frame_duration = FRAME_DURATION_OVERRIDES[file_list[current_image]]



def advance_image():
    """
    Advance to the next image in the list and loop back at the end
    """
    # pylint: disable=global-statement
    global current_image
    if current_image is not None:
        current_image += 1
    if current_image is None or current_image >= len(file_list):
        current_image = 0
    load_image()


def advance_frame():
    """
    Advance to the next frame and loop back at the end


    can we construct a 
    """
    # pylint: disable=global-statement
    global current_frame, current_loop
    current_frame = current_frame + 1
    if current_frame >= frame_count:
        current_frame = 0
        current_loop = current_loop + 1
    sprite_group[0][0] = current_frame


advance_image()


# tony_audio.play("wav/tudum.wav")
# time.sleep(5)



is_tudum = False

# Set the delay interval (0.1 seconds)
delay_interval = 0.1

# Record the starting time
last_time = time.monotonic()

# from adafruit_display_text import label


# text = "Hello! \nI am #0 of my kind."
# text_area = label.Label(terminalio.FONT, text=text, scale=1, background_color=0x100000, )
# text_area.x = 0
# text_area.y = 5
# # text_area.anchor_point = (-.5, .4)
# # text_area.anchored_position = (.4, .5)
# matrix.display.root_group  = text_area
# while True:
#     pass

# tony_audio.play("wav/tudum.wav")
# while True:
#     pass

current_time = time.monotonic()
is_muted = False

def check_mute():

    global is_muted, button_down
        # mute handling
    button_down.update()
    if button_down.fell:
        is_muted = not is_muted
        if tony_audio.audio_output is not None:
            tony_audio.stop()
        


while True:
    if auto_advance and current_loop >= AUTO_ADVANCE_LOOPS:
        advance_image()

    # This uses the global audio_output which is set up once
    if not is_tudum and has_double_tap():
        # print("double tap detected!", is_tudum)
        if not is_tudum:
            is_tudum = True
            handle_tudum()
            is_tudum = False
    else:
        pass


    time.sleep(0.01)
    
    current_time = time.monotonic()
    # Check if the time interval has elapsed
    if current_time - last_time >= delay_interval:
        # Place the code to execute every `delay_interval` seconds here
        
        check_mute()


        advance_frame()
        # Reset the last_time to the current time
        last_time = current_time

