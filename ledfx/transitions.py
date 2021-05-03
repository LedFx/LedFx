import numpy as np


class IterClass(type):
    def __iter__(cls):
        yield from getattr(cls, "NAMED_FUNCTIONS").keys()


class Transitions(metaclass=IterClass):
    def __init__(self, pixel_count, max_brightness=1, min_brightness=0):
        self.pixel_count = pixel_count
        self.max_brightness = max_brightness
        self.min_brightness = min_brightness
        self.dissolve_array = np.random.rand(pixel_count)
        i = np.linspace(1, 0, pixel_count)
        # This monstrosity fixes the creation of an array of i+1 length for uneven arrays,
        # breaking transitions on unevenly sized arrays
        # [-1::-2] or [-2::-2]
        # https://discord.com/channels/469985374052286474/785654790247546941/835507683129032725
        self.iris_array = np.concatenate([i[::2], i[-1 + len(i) % -2 :: -2]])

    def __getitem__(cls, mode):
        return getattr(cls, "NAMED_FUNCTIONS")[mode]

    def __setitem__(cls, mode):
        raise Exception("Don't you be setting these values cheeky ;)")

    def _validate(x1, x2, weight):
        assert np.shape(x1) == np.shape(x2)
        assert 0 <= weight <= 1

    def add(self, x1, x2, weight):
        """
        weighted additive blending of x1 and x2
        operates on x1 directly
        """
        np.multiply(x1, weight, x1)
        x3 = np.multiply(x2, 1 - weight)
        np.add(x1, x3, x1)

    def dissolve(self, x1, x2, weight):
        """
        random indexes of x1 are set to the value of x2
        roughly proportional in quantity to weight
        """
        indexes = np.greater(self.dissolve_array, weight)
        x1[indexes, :] = x2[indexes, :]

    def push(self, x1, x2, weight):
        """
        x1 "pushes" x2 to the side, proportional to weight
        """
        idx = int((1 - weight) * self.pixel_count)
        x2 = np.roll(x2, idx, axis=0)
        x1[:idx, :] = x2[:idx, :]

    def slide(self, x1, x2, weight):
        """
        x1 overlaps x2 from the side, proportional to weight
        """
        idx = int((1 - weight) * self.pixel_count)
        x1[:idx, :] = x2[:idx, :]

    def iris(self, x1, x2, weight):
        """
        x2 overlaps x1 from the centre, proportional to weight
        """
        indexes = np.greater(self.iris_array, weight)
        x1[indexes, :] = x2[indexes, :]

    def throughWhite(self, x1, x2, weight):
        """
        fades x1 into white, then out into x2
        """
        if weight < 0.5:
            np.clip(x2, weight * 2 * 255, None, out=x1)
        else:
            np.clip(x1, (1 - weight) * 2 * 255, None, out=x1)

    def throughBlack(self, x1, x2, weight):
        """
        fades x1 into black, then out into x2
        """
        if weight < 0.5:
            np.clip(x2, None, 255 * (1 - (weight * 2)), x1)
        else:
            np.clip(x1, None, 255 * 2 * (weight - 0.5), x1)

    NAMED_FUNCTIONS = {
        "Add": add,
        "Dissolve": dissolve,
        "Push": push,
        "Slide": slide,
        "Iris": iris,
        "Through White": throughWhite,
        "Through Black": throughBlack,
        "None": "None",
    }
