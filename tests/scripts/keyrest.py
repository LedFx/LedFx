import keyboard
import requests
import os

# this test script will on the pressing of the space bar send a request to the ledfx server 
# to change the effect of a virtual to my_effect with the fallback value of 20 seconds
# On release of the space bar it will cancel the effect and fallback to the previous effect
# exit by pressing X. the terminal does not need to be in focus for this to work

my_virtual = "wled19-32x32"
my_effect = "noise2d"
was_pressed = False


def on_space_press():
    global was_pressed
    if not was_pressed:
        print("Space bar pressed")
        payload = {"type": my_effect, "fallback": 20}
        response = requests.post(f'http://127.0.0.1:8888/api/virtuals/{my_virtual}/effects', json=payload)
        print(f"Response: {response.status_code} - {response.text}")
        was_pressed = True


def on_space_release():
    global was_pressed
    print("Space bar released")
    response = requests.get(f'http://127.0.0.1:8888/api/virtuals/{my_virtual}/fallback')
    print(f"Response: {response.status_code} - {response.text}")

    was_pressed = False


def press_x():
    print('X key pressed, everyone out of the sewers...')
    os._exit(0)


def main():
    # Register event handlers for space bar press and release
    keyboard.on_press_key('space', lambda _: on_space_press())
    keyboard.on_release_key('space', lambda _: on_space_release())

    # Monitor for 'X' or 'x' key press to exit the program
    keyboard.add_hotkey('x', lambda: press_x())
    keyboard.add_hotkey('X', lambda: press_x())

    # Block the program and keep it running
    keyboard.wait()


if __name__ == "__main__":
    main()