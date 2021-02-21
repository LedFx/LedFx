import numpy as np


class IterClass(type):
    def __iter__(cls):
        for mode in getattr(cls, "NAMED_FUNCTIONS").keys():
            yield mode


class Blender(metaclass=IterClass):
    def __init__(self, pixel_count, max_brightness=1, min_brightness=0):
        self.pixel_count = pixel_count
        self.max_brightness = max_brightness
        self.min_brightness = min_brightness
        self.dissolve_array = np.random.rand(pixel_count)
        i = np.linspace(1, 0, pixel_count)
        self.iris_array = np.concatenate([i[::2], i[-1::-2]])

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

    def subtract(self, x1, x2, weight):
        """
        weighted subtractive blending of x1 and x2
        operates on x1 directly
        """
        np.multiply(x1, weight, x1)
        x3 = np.multiply(x2, 1 - weight)
        np.subtract(x1, x3, x1)

    def multiply(self, x1, x2, weight):
        """
        weighted multiplicative blending of x1 and x2
        operates on x1 directly
        """
        np.multiply(x1, weight, x1)
        x3 = np.multiply(x2, 1 - weight)
        np.multiply(x1, x3, x1)
        np.divide(x1, self.max_brightness, x1)

    def divide(self, x1, x2, weight):
        """
        weighted divisive blending of x1 and x2
        operates on x1 directly
        """
        np.multiply(x1, weight, x1)
        x3 = np.multiply(x2, 1 - weight)
        np.divide(x1, x3, where=x3 > 0, out=x1)
        np.multiply(x1, self.max_brightness, x1)

    def dissolve(self, x1, x2, weight):
        """
        random indexes of x1 are set to the value of x2
        roughly proportional in quantity to weight
        """
        indexes = np.greater(self.dissolve_array, weight)
        x1[indexes, :] = x2[indexes, :]

    def push(self, x1, x2, weight):
        """
        x2 "pushes" x1 to the side, proportional to weight
        """
        idx = int(weight * self.pixel_count)
        np.roll(x1, idx, axis=1)
        x1[:idx, :] = x2[:idx, :]

    def slide(self, x1, x2, weight):
        """
        x2 overlaps x1 from the side, proportional to weight
        """
        idx = weight * self.pixel_count
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
            np.clip(x1, weight * 2, None, x1)
        else:
            np.clip(x2, (1 - weight) * 2, None, x1)

    def throughBlack(self, x1, x2, weight):
        """
        fades x1 into black, then out into x2
        """
        if weight < 0.5:
            np.clip(x1, None, 1 - (weight * 2), x1)
        else:
            np.clip(x2, None, 2 * (weight - 0.5), x1)

    NAMED_FUNCTIONS = {
        "Add": add,
        "Subtract": subtract,
        "Multiply": multiply,
        "Divide": divide,
        "Dissolve": dissolve,
        "Push": push,
        "Slide": slide,
        "Iris": iris,
        "Through White": throughWhite,
        "Through Black": throughBlack,
    }
