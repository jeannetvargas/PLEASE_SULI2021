'''
Jeannet Vargas BNL SULI 2021 added file

Create new file to add a window to adjust image -- this would have all the info
of pop up window when "Adjust" is clicked from Image menu bar

Currently links call from please.py Image menu bar opening and opens a window with
button and way text entry to get a path and print it.

These were used to start the imaging enhancing function

'''
import os
from PyQt5 import QtCore, QtWidgets
from PIL import Image, ImageEnhance
import numpy as np
import LEEMFUNCTIONS as LF
from qthreads import WorkerThread
from experiment import Experiment


'''
Created new class to open individual image file

class newImageAdjust(QtWidgets.QWidget):
    path = '/Users/net/BigOneDrive/BNL/Software_Data_BNL/DATA_LEEM_IV_Second_Day/'

    firstimage = []

    ht = 600
    wd = 592
    bitsize = 16
    byte = 'L'
    
    getFile = [name for name in os.listdir(path) if name.endswith('.dat') ]
    for ff in getFile:
        with open(os.path.join(path,'LEEM_IV__000_000.dat'),'rb') as f_f:
            handle = len(f_f.read()) - (int(bitsize/8) * ht * wd)
            f_f.seek(0)
            if bitsize ==16 and byte == 'L':
                formatstring = '<u2'
            firstimage.append(np.frombuffer(f_f.read() [handle:],formatstring).reshape((ht,wd)))

    newfirstImage = np.dstack(firstimage)
    del firstimage[:]
    print(newfirstImage)

    print(newfirstImage.shape)
    print(type(newfirstImage))


    image = cv.imread('/Users/net/BigOneDrive/BNL/Software_Data_BNL/DATA_LEEM_IV_Second_Day/LEEM_IV__000_000.dat/')
    shapedImage = newfirstImage.reshape(-1,2)
    
    plt.imshow(shapedImage, cmap = 'gray', interpolation = 'nearest')
    print(shapedImage)
    print(shapedImage.shape)
    print(shapedImage.dtype)
    
    cvImage = shapedImage.astype(np.uint8)
    print(cvImage.dtype)
    cv.namedWindow('new window')
    cv.imshow('new window', cvImage)
    cv.waitKey(0)
'''

class ImageAdjust(QtWidgets.QWidget):
    """UI widget to generate adjust pop up """



    def __init__(self):# taken from yamloutput.py code --> path entry and button
        super(ImageAdjust, self).__init__()
        self.setupImageLayout()
        self.dataPath = None
        self.pathButton.clicked.connect(self.getImagePath)
        self.brightbutton.clicked.connect(self.EnhanceButton)
        self.setWindowTitle("Enter Image Enhancement")
        self.show()        
        

    def getImagePath(self): #need to locate path of image to use pillow
        path = QtWidgets.QFileDialog.getExistingDirectory(self, "Get path")
        if isinstance(path, tuple) and len(path) != 0:
            path = str(path[0])
        if path != "":
            self.dataPath = path
            self.pathText.setReadOnly(False)
            self.pathText.setText(path)
            self.pathText.setReadOnly(True)
        print('Selected path to Image: ', self.dataPath)

       
        
        
        
        
    def EnhanceButton(self):# When enhance button is clicked create trackbar and
        #open new window
        def value(x):
            print(x)
        image = np.full((300,300,3),255).astype(np.uint8)
        cv.namedWindow('Enhance Image')
        cv.createTrackbar('Adjust','Enter Image Enhancement',0,500,value)
        cv.imshow('Enhance Image',image)
        cv.waitKey(0)
# try to adjust first image file in this path: from LEEMFUNCTIONS.py file
        path = '/Users/net/BigOneDrive/BNL/Software_Data_BNL/DATA_LEEM_IV_Second_Day/'

        firstimage = []

        ht = 600
        wd = 592
        bitsize = 16
        byte = 'L'
        
        getFile = [name for name in os.listdir(path) if name.endswith('.dat') ]
        for ff in getFile:
            with open(os.path.join(path,'LEEM_IV__000_000.dat'),'rb') as f_f:
                handle = len(f_f.read()) - (int(bitsize/8) * ht * wd)
                f_f.seek(0)
                if bitsize ==16 and byte == 'L':
                    formatstring = '<u2'
                firstimage.append(np.frombuffer(f_f.read() [handle:],formatstring).reshape((ht,wd)))

        newfirstImage = np.dstack(firstimage)
        del firstimage[:]
        print(newfirstImage)

        print(newfirstImage.shape)
        print(type(newfirstImage))


        image = cv.imread('/Users/net/BigOneDrive/BNL/Software_Data_BNL/DATA_LEEM_IV_Second_Day/LEEM_IV__000_000.dat/')
        shapedImage = newfirstImage.reshape(-1,2)
    
        plt.imshow(shapedImage, cmap = 'gray', interpolation = 'nearest')
        print(shapedImage)
        print(shapedImage.shape)
        print(shapedImage.dtype)
        
        cvImage = shapedImage.astype(np.uint8)
        print(cvImage.dtype)
        cv.namedWindow('new window')
        cv.imshow('new window', cvImage)
        cv.waitKey(0)



        
        
        

    def setupImageLayout(self): #UI widget (window)
        mainVBox = QtWidgets.QVBoxLayout()

       
        #path -- copied from LEEMfunctions.py 
        pathHBox = QtWidgets.QHBoxLayout()
        pathHBox.addStretch()
        pathLabel = QtWidgets.QLabel("Click to select data path of image:")
        pathHBox.addWidget(pathLabel)
        self.pathButton = QtWidgets.QPushButton("Select Path", self)
        pathHBox.addWidget(self.pathButton)
        self.pathText = QtWidgets.QLineEdit()
        self.pathText.setReadOnly(True)
        pathHBox.addWidget(self.pathText)
        mainVBox.addLayout(pathHBox)
        
         #input for Brightness
        brightHBox = QtWidgets.QHBoxLayout()
        brightLabel = QtWidgets.QLabel("Adjust Brightness:")
        brightHBox.addWidget(brightLabel)
        self.brightbutton = QtWidgets.QPushButton('Enhance', self)
        brightHBox.addWidget(self.brightbutton)
        mainVBox.addLayout(brightHBox)

        
        






        self.setLayout(mainVBox)
    



