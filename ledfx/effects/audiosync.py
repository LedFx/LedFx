import numpy as np

# tuneable parameters
# these are the window sizes used to calculate the short and long term averages
# highly dependent on the sample rate of the audio
SHORT_WINDOW_SIZE = 5
LONG_WINDOW_SIZE = 80

class AudioSync:
    '''
    AudioSync is a class that implements the realtime audio segmentation algorithm AudioSync
    https://github.com/not-matt/AudioSync
    '''
    def __init__(self, audio):
        self._audio = audio
        self.feature_history = np.zeros((LONG_WINDOW_SIZE, 3))
        self.short_term_average = np.zeros(3)
        self.long_term_average = np.zeros(3)
    
    def __call__(self):
        # calculate the features of the current audio frame
        lfc = self.calculateLFC(self._audio.frequency_domain().norm)
        energy = self.calculateEnergy(self._audio.audio_sample())
        zcr = self.calculateZCR(self._audio.audio_sample())
        # grab the outgoing feature vector of the short term average
        self.long_oldest_feature = self.feature_history[-1]
        # grab the outgoing feature vector of the short term average
        self.short_oldest_feature = self.feature_history[SHORT_WINDOW_SIZE]
        # update the feature history with the new feature vector
        self.feature_history = np.roll(self.feature_history, 1, axis=0)
        self.feature_history[0][0] = lfc
        self.feature_history[0][1] = energy
        self.feature_history[0][2] = zcr
        # update the short and long term averages
        self.short_term_average += self.feature_history[0] - self.short_oldest_feature
        self.long_term_average += self.short_oldest_feature - self.long_oldest_feature
        # calculate the squared distance between the short and long term averages
        squared_distance = self.calculateSquaredDistance(self.short_term_average, self.long_term_average)
        # do something smarter with the squared distance (todo: thresholding, graphing)
        # print(squared_distance)
        return squared_distance
    
    # calculates the low frequency content of the audio
    # directly correlates to the low frequency content of the audio
    def calculateLFC(self, spectrum):
        startIndex = 0
        endIndex = int(np.ceil(len(spectrum) * 0.05)) # this could be a constant using freq_domain_length
        sum_val = np.sum(spectrum[startIndex:endIndex+1])
        total = endIndex - startIndex + 1
        return sum_val / total if total > 0 else 0

    # calculates the total energy of the audio
    # roughly but not exclusively correlates to the low frequency content of the audio
    def calculateEnergy(self, frame):
        if not isinstance(frame, np.ndarray):
            return 0
        # frame = np.array(frame) # check type. might already be np.array
        energy = np.sum(frame * frame)
        return energy 

    # calculates the zero crossing rate of the audio, which is the number of times the audio crosses the x axis
    # roughly correlates to the high frequency content of the audio
    def calculateZCR(self, frame):
        if not isinstance(frame, np.ndarray):
            return 0
        zcr = np.sum(np.diff(np.sign(frame)) != 0)
        return zcr
    
    # function to calculate the squared distance between two vectors
    # this is like euclidian distance, but by skipping the sqrt and comparing squared values, we can save some processing power
    def calculateSquaredDistance(self, vector1: np.array, vector2: np.array) -> float:
        squared_diff = np.power(vector1 - vector2, 2)
        sum_squared_diff = np.sum(squared_diff)
        squared_distance = np.power(sum_squared_diff, 2)
        return squared_distance