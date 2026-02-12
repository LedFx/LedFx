import time

import requests

# This test script generates fallback triggers and clears for LedFx virtuals.
# Timings are driven as per the table in the code. 100s of events at high and slow speed
# use the test config scenes_playlists.json for simple compatibility
# or edit virtuals list to use against other configurations

virtuals = ["dummy1", "dummy2", "dummy3", "dummy4"]
my_effect = "noise2d"
was_pressed = False


def on_space_press():
    global was_pressed
    if not was_pressed:
        payload = {"type": my_effect, "fallback": 20}
        for v in virtuals:
            response = requests.post(
                f"http://127.0.0.1:8888/api/virtuals/{v}/effects",
                json=payload,
            )
            print(f"Response ({v}): {response.status_code} - {response.text}")
        was_pressed = True


def on_space_release():
    global was_pressed
    for v in virtuals:
        response = requests.get(
            f"http://127.0.0.1:8888/api/virtuals/{v}/fallback"
        )
        print(f"Response ({v}): {response.status_code} - {response.text}")
    was_pressed = False


def main():
    # Simulate space bar presses and releases with varying timings
    # data table format is
    # | Timing (s) | Number of Events |
    # where timing is used for both key down and key up period
    timings = (
        [0.03] * 50
        + [0.1] * 50
        + [0.2] * 20
        + [0.5] * 20
        + [1.0] * 10
        + [0.03] * 20
    )
    for t in timings:
        on_space_press()
        time.sleep(t)
        on_space_release()
        time.sleep(t)
    print("Simulation complete.")


if __name__ == "__main__":
    main()
