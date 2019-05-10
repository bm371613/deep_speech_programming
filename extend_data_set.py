#! /bin/env python
import contextlib
import csv
import io
import pathlib
import re
import sys
import wave

import pyaudio


class Audio:

    def __init__(self):
        self.pa = pyaudio.PyAudio()

    @contextlib.contextmanager
    def record(self, f, channels=1, rate=16000, frames_per_buffer=1024):
        with wave.open(f, 'wb') as wf:
            wf.setnchannels(channels)
            wf.setframerate(rate)
            wf.setsampwidth(self.pa.get_sample_size(pyaudio.paInt16))

            def stream_callback(data, *_):
                wf.writeframes(data)
                return data, pyaudio.paContinue

            stream = self.pa.open(
                stream_callback=stream_callback,
                format=pyaudio.paInt16,
                input=True,
                channels=channels,
                rate=rate,
                frames_per_buffer=frames_per_buffer,
            )
            stream.start_stream()
            yield
            stream.stop_stream()
            stream.close()

    def play(self, f, chunk=1024):
        wf = wave.open(f, 'rb')
        stream = self.pa.open(
            format=self.pa.get_format_from_width(wf.getsampwidth()),
            channels=wf.getnchannels(),
            rate=wf.getframerate(),
            output=True,
        )
        data = wf.readframes(chunk)
        while data:
            stream.write(data)
            data = wf.readframes(chunk)
        stream.close()

    def close(self):
        self.pa.terminate()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


class DataSet:

    def __init__(self, path: pathlib.Path):
        self.path = path
        self.index_path = path / 'index.csv'
        self.records_dir = path / 'records'
        self.index = []
        if self.index_path.exists():
            with self.index_path.open() as f:
                self.index.extend(csv.DictReader(f))

    def add(self, transcript, record_data):
        slug = "_".join(re.findall(r"\w+", transcript))
        i = 0
        while True:
            record_path = self.records_dir / f'{slug}-{i}.wav'
            if not record_path.exists():
                break
            i += 1
        self.index.append(dict(
            wav_filename=str(record_path.relative_to(self.path)),
            wav_filesize=len(record_data),
            transcript=transcript,
        ))
        self.records_dir.mkdir(parents=True, exist_ok=True)
        record_path.write_bytes(record_data)
        with self.index_path.open('w') as f:
            w = csv.DictWriter(f, fieldnames=('wav_filename', 'wav_filesize', 'transcript'))
            w.writeheader()
            w.writerows(self.index)


def input_or_exit(*args, **kwargs):
    try:
        return input(*args, **kwargs)
    except EOFError:
        print("\nBye!")
        sys.exit(0)


def main():
    if len(sys.argv) != 2 or sys.argv[1] in ('-h', '--help'):
        print(f"Usage: {sys.argv[0]} <data set directory>")
        sys.exit(1)
    data_set = DataSet(pathlib.Path(sys.argv[1]))
    with Audio() as audio:
        while True:
            input_or_exit(f'Hit Enter to start recording, then hit Enter again to stop.')
            f = io.BytesIO()
            with audio.record(f):
                input_or_exit("Recording. Hit Enter to stop")
            f.seek(0)
            print(f'Listen to what was recorded.')
            audio.play(f)
            f.seek(0)
            transcript = input_or_exit(
                "Type the transcript, or just hit Enter to record again: "
            ).lower().strip()
            if transcript:
                data_set.add(transcript, f.getvalue())
                print("Saved!")
            print()


if __name__ == '__main__':
    main()
