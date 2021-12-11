import glob
import os

import imageio
import matplotlib
import numpy as np
from matplotlib import pyplot as plt

# Run this to visualise all effectlets as pngs + gifs

for npyfilename in glob.glob("*.npy"):
    # png
    img_array = np.load(npyfilename, allow_pickle=True)
    plt.imshow(img_array, cmap="gray")
    img_name = npyfilename.replace(".npy", "")
    matplotlib.image.imsave(img_name + ".png", img_array)
    plt.close()

    # gif
    filenames = []
    for i in range(len(img_array)):
        # just grab 1 row
        my_row = np.array([img_array[i]])
        plt.imshow(my_row, cmap="gray")
        matplotlib.image.imsave(f"{i}.png", my_row)
        # create file name and append it to a list
        filename = f"{i}.png"
        filenames.append(filename)
        plt.close()
    # build gif
    with imageio.get_writer(img_name + ".gif", mode="I") as writer:
        for filename in filenames:
            image = imageio.imread(filename)
            writer.append_data(image)
    # Remove files
    for filename in set(filenames):
        os.remove(filename)
