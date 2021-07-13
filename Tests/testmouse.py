"""Test Mouse Coordinates for PyQtGraph."""
import numpy as np
from PyQt5 import QtWidgets
import pyqtgraph as pg
import sys


class Test(object):
    """Create test image for testing mouse click in pyqtgraph.

    Link mouse clicked signal to a function that pulls pixel
    values from the image being displayed at the location of click.
    """

    def __init__(self):
        """."""
        self.testdata = np.zeros((600, 600))
        self.testdata[0:300, 0:300] = 255  # top left white
        self.testdata[0:300, 300:] = 175  # top right light gray
        self.testdata[300:, 300:] = 95  # bottom right dark gray
        # bottom left black

        #####################
        #         #         #
        #   W     #  LG     #
        #         #         #
        #####################
        #         #         #
        #   B     #  DG     #
        #         #         #
        #####################

        # Pyqtgraph interprets the array as [width, height]
        # This is reversed from the Numpy convention
        # Here we apply a horizontal flip via [::-1, :] then transpose the array
        # This is equivalent to a 90 degree CCW rotation of the array.
        # The result is a pyqtgraph display which matches the original array shown above.
        self.image = pg.ImageItem(self.testdata[::-1, :].T)
        self.plotwidget = pg.PlotWidget()
        self.plotwidget.addItem(self.image)

        # mouse click signal
        self.sigmc = self.image.scene().sigMouseClicked
        self.sigmc.connect(self.handleClick)
        self.plotwidget.show()

    def handleClick(self, event):
        """Print out click coordinates and array value from click location.

        Clicking in the image squares should correctly print out the pixel value
        corresponding to the color of the square:
        White = 255, Light Gray = 175, Dark Gray = 95, Black = 0.

        If the incorrect pixel values are printed, or if the image displayed does not
        match the layout presented in __init__(), then the coordinate mapping is not
        correct.
        """
        if event.currentItem is None:
            return
        vb = self.plotwidget.getPlotItem().getViewBox()
        mp = vb.mapSceneToView(event.scenePos())
        x = int(mp.x())
        y = int(mp.y())
        print("Click Coordinates: x={0}, y={1}".format(x, y))
        y = (self.testdata.shape[0] - 1) - y  # flip y coordinate so that upper edge of image is 0.
        print("Mapped Position: x={0}, y={1}".format(x, y))
        if x >= 0 and x <= 599 and y >= 0 and y <= 599:
            print("Pixel Value: {0}".format(self.testdata[y, x]))
        else:
            print("Click originating outside Image Area. No Pixel Value.")


def main():
    """Create QApplication instance, then show the main test window."""
    app = QtWidgets.QApplication(sys.argv)
    test = Test()
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
