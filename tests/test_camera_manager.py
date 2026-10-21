import importlib
import io
import threading
import time


def test_streaming_output_implements_buffered_io_contract():
    camera_module = importlib.import_module("backend.src.camera.camera_manager")

    assert isinstance(camera_module.StreamingOutput(), io.BufferedIOBase)


def test_streaming_output_waits_for_a_new_frame():
    camera_module = importlib.import_module("backend.src.camera.camera_manager")
    output = camera_module.StreamingOutput()
    output.write(b"\xff\xd8first frame")
    frames = output.frames()
    first = next(frames)
    second_result = []
    second_frame_received = threading.Event()

    def read_next_frame():
        second_result.append(next(frames))
        second_frame_received.set()

    reader = threading.Thread(target=read_next_frame)
    reader.start()
    try:
        assert not second_frame_received.wait(0.05)
        output.write(b"\xff\xd8second frame")
        assert second_frame_received.wait(1)
    finally:
        reader.join(1)

    assert b"first frame" in first
    assert b"second frame" in second_result[0]


def test_concurrent_start_initializes_camera_once(monkeypatch):
    camera_module = importlib.import_module("backend.src.camera.camera_manager")
    initialization_entered = threading.Event()
    continue_initialization = threading.Event()
    second_start_attempted = threading.Event()
    second_start_finished = threading.Event()
    instance_count_lock = threading.Lock()
    instance_count = 0

    class FakeCamera:
        def __init__(self):
            nonlocal instance_count
            with instance_count_lock:
                instance_count += 1
                is_first_instance = instance_count == 1
            if is_first_instance:
                initialization_entered.set()
                if not continue_initialization.wait(2):
                    raise TimeoutError("test did not release camera initialization")

        def create_video_configuration(self, **kwargs):
            return kwargs

        def configure(self, configuration):
            pass

        def start_recording(self, encoder, output):
            pass

        def stop_recording(self):
            pass

        def close(self):
            pass

    monkeypatch.setattr(camera_module, "Picamera2", FakeCamera)
    monkeypatch.setattr(camera_module, "JpegEncoder", lambda **kwargs: object())
    monkeypatch.setattr(camera_module, "FileOutput", lambda output: output)
    manager = camera_module.CameraManager()
    errors = []

    def start_manager():
        try:
            manager.start()
        except Exception as error:
            errors.append(error)

    def start_manager_again():
        second_start_attempted.set()
        start_manager()
        second_start_finished.set()

    first = threading.Thread(target=start_manager)
    second = threading.Thread(target=start_manager_again)
    first.start()
    assert initialization_entered.wait(1)
    second.start()

    try:
        assert second_start_attempted.wait(1)
        time.sleep(0.05)
        assert not second_start_finished.is_set()
    finally:
        continue_initialization.set()
        first.join(2)
        second.join(2)

    assert not first.is_alive()
    assert not second.is_alive()
    assert not errors
    assert instance_count == 1
    assert second_start_finished.is_set()
    assert manager.running
    manager.stop()