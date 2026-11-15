"""Audio capture and analysis in a process of its own.

Python runs one thread at a time per interpreter. In the LedFx process the
audio thread shares that with every virtual's render thread, the event loop
and the API, and with several active virtuals it falls behind the audio device
and drops blocks. Here capture and AudioAnalyzer run in a separate process with
an interpreter of its own, and only each block's results travel back.

worker.py is the audio process. client.py is the LedFx side: it starts the
worker, opens and closes sources in it and hands each block's results to
AudioAnalysisSource. protocol.py is the framing between the two.
"""
