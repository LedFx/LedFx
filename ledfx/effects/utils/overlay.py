from ledfx.utils import get_mono_font


class Overlay():
    def __init__(self, r_height, r_width):
        self.r_height = r_height
        self.r_width = r_width
        self.diag_font = get_mono_font(10)

    def plot_range(self, values, color):
        diag_string = "None"
        if len(values) > 1:

            graph_s = 9  # start pixel height under the diag text
            graph_h = max(1, self.r_height - 9 - 1)  # height of graph
            v_min = min(values)
            v_max = max(values)
            if v_max == v_min:
                v_min = min(0, v_min)
                v_max = max(0, v_max)
            v_range = v_max - v_min
            x = 0
            pixels = self.image.load()
            for value in reversed(values):
                value_norm = (value - v_min) / v_range
                y = graph_s + graph_h - (value_norm * graph_h)
                if y < self.r_height:
                    if value == 0:
                        pixels[x, y] = (0, 255, 255)
                    else:
                        pixels[x, y] = color
                x += 1
                if x >= self.r_width:
                    break

            diag_string = f"{values[-1]} {v_min} {v_max} {v_range}"
        return diag_string

    def render(self, m_image, m_draw, values, values2=None, values3=None):
        self.image = m_image
        diag_string = self.plot_range(values, (255, 0, 0))
        if values2 is not None:
            self.plot_range(values2, (0, 255, 0))
        if values3 is not None:
            self.plot_range(values3, (0, 0, 255))
        m_draw.text((0, 0), diag_string, fill='yellow', font=self.diag_font)