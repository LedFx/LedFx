import os

try:
    import keyboard
    import requests
except ImportError as e:
    print(f"Required package not found: {e}")
    print("Please install required packages: pip install keyboard requests")
    exit(1)
# this test script will on the pressing of the space bar send a request to the ledfx server
# to Fire onshot on a profile across all virtuals
# multiple presses will override any active oneshot

space_pressed = False
v_pressed = False
b_pressed = False


# space give a fast white flash with no release behaviour
def on_space_press():
    global space_pressed
    if not space_pressed:
        print("Space bar pressed")
        send_oneshot("white", 50, 50, 100, 1)
        space_pressed = True


def on_space_release():
    global space_pressed
    print("Space bar released")
    space_pressed = False


# v gives a long ramp, hold, fade, with a hard clear on key release
def on_v_press():
    global v_pressed
    if not v_pressed:
        print("v bar pressed")
        send_oneshot("red", 1000, 1000, 2000, 1)
        v_pressed = True


def on_v_release():
    global v_pressed
    print("v bar released")
    send_oneshot("red", 0, 0, 0, 1)
    v_pressed = False


# b gives a long ramp, hold, fade, with no key release behaviour
def on_b_press():
    global b_pressed
    if not b_pressed:
        print("b bar pressed")
        send_oneshot("blue", 1000, 1000, 2000, 1)
        b_pressed = True


def on_b_release():
    global b_pressed
    print("b bar released")
    b_pressed = False


def send_oneshot(color, ramp, hold, fade, brightness):
        payload = {
            "tool":"oneshot",
            "color":color,
            "ramp":ramp,
            "hold":hold,
            "fade":fade,
            "brightness":brightness
        }

        try:
            response = requests.put(
                f"http://127.0.0.1:8888/api/virtuals_tools",
                json=payload,
            )
            print(f"Response: {response.status_code} - {response.text}")
        except Exception as e:
            print(f"Request failed: {e}")


def press_x():
    print("X key pressed, everyone out of the sewers...")
    os._exit(0)


def main():
    # Register event handlers for space bar press and release
    keyboard.on_press_key("space", lambda _: on_space_press())
    keyboard.on_release_key("space", lambda _: on_space_release())

    # register event handlers for v press and release
    keyboard.on_press_key("v", lambda _: on_v_press())
    keyboard.on_release_key("v", lambda _: on_v_release())

    # register event handlers for b press and release
    keyboard.on_press_key("b", lambda _: on_b_press())
    keyboard.on_release_key("b", lambda _: on_b_release())

    # Monitor for 'X' or 'x' key press to exit the program
    keyboard.add_hotkey("x", lambda: press_x())
    keyboard.add_hotkey("X", lambda: press_x())

    # Block the program and keep it running
    keyboard.wait()


if __name__ == "__main__":
    main()
