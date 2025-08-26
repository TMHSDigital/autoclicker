"""
Click engine for the autoclicker
Handles mouse clicking operations with safety checks
"""

import time
import random
import threading
import statistics
from collections import deque
from typing import Callable, Optional, Dict, List

import pyautogui

from .exceptions import ClickEngineError, CoordinateError, SafetyError, create_user_friendly_error

# Disable pyautogui failsafe for production use
pyautogui.FAILSAFE = False


class ClickEngine:
    """Handles mouse clicking operations with threading and safety features"""

    def __init__(self, enable_performance_monitoring: bool = True):
        self.is_running = False
        self.click_thread: Optional[threading.Thread] = None
        self.click_count = 0
        self.start_time = 0
        self._stop_event = threading.Event()

        # Performance monitoring
        self.enable_performance_monitoring = enable_performance_monitoring
        self.performance_metrics = {
            'click_timings': deque(maxlen=1000),  # Store last 1000 click timings
            'click_success_count': 0,
            'click_error_count': 0,
            'average_click_time': 0.0,
            'min_click_time': float('inf'),
            'max_click_time': 0.0,
            'total_click_time': 0.0,
            'cpu_usage_samples': deque(maxlen=100),
            'memory_usage_samples': deque(maxlen=100)
        }

        # Click queuing for high-frequency operations
        self.click_queue: deque = deque()
        self.queue_processor_thread: Optional[threading.Thread] = None
        self.max_queue_size = 1000
        self.enable_queuing = False

    def start_clicking(self, x: int, y: int, interval: float, variation: int,
                      burst_clicks: int, burst_pause: float, max_clicks: int,
                      auto_stop_minutes: int, mouse_button: str, click_type: str,
                      on_click_complete: Optional[Callable] = None,
                      on_status_update: Optional[Callable] = None) -> bool:
        """
        Start the clicking process

        Args:
            x, y: Target coordinates
            interval: Base interval between clicks (ms)
            variation: Random variation range (±ms)
            burst_clicks: Number of clicks per burst
            burst_pause: Pause between bursts (seconds)
            max_clicks: Maximum clicks (0 = unlimited)
            auto_stop_minutes: Auto-stop after minutes (0 = disabled)
            mouse_button: 'left', 'right', or 'middle'
            click_type: 'single' or 'double'
            on_click_complete: Callback when clicking finishes
            on_status_update: Callback for status updates

        Returns:
            True if started successfully, False otherwise
        """
        if self.is_running:
            return False

        # Reset state
        self.is_running = True
        self.click_count = 0
        self.start_time = time.time()
        self._stop_event.clear()

        # Start click thread
        self.click_thread = threading.Thread(
            target=self._click_loop,
            args=(x, y, interval, variation, burst_clicks, burst_pause,
                  max_clicks, auto_stop_minutes, mouse_button, click_type,
                  on_click_complete, on_status_update),
            daemon=True
        )
        self.click_thread.start()

        return True

    def get_performance_metrics(self) -> Dict:
        """Get current performance metrics"""
        metrics = self.performance_metrics.copy()

        # Calculate additional metrics
        total_clicks = metrics['click_success_count'] + metrics['click_error_count']
        if total_clicks > 0:
            metrics['success_rate'] = (metrics['click_success_count'] / total_clicks) * 100
        else:
            metrics['success_rate'] = 0.0

        if metrics['click_timings']:
            metrics['average_click_time'] = statistics.mean(metrics['click_timings'])
            metrics['median_click_time'] = statistics.median(metrics['click_timings'])
            metrics['click_time_std_dev'] = statistics.stdev(metrics['click_timings']) if len(metrics['click_timings']) > 1 else 0.0

        # Calculate clicks per second if running
        if self.start_time > 0 and self.click_count > 0:
            runtime = time.time() - self.start_time
            metrics['clicks_per_second'] = self.click_count / runtime if runtime > 0 else 0.0

        return metrics

    def reset_performance_metrics(self) -> None:
        """Reset all performance metrics"""
        self.performance_metrics = {
            'click_timings': deque(maxlen=1000),
            'click_success_count': 0,
            'click_error_count': 0,
            'average_click_time': 0.0,
            'min_click_time': float('inf'),
            'max_click_time': 0.0,
            'total_click_time': 0.0,
            'cpu_usage_samples': deque(maxlen=100),
            'memory_usage_samples': deque(maxlen=100)
        }

    def enable_click_queuing(self, enable: bool = True, max_queue_size: int = 1000) -> None:
        """Enable or disable click queuing for high-frequency operations"""
        self.enable_queuing = enable
        self.max_queue_size = max_queue_size

        if enable and not self.queue_processor_thread:
            self._start_queue_processor()
        elif not enable and self.queue_processor_thread:
            self._stop_queue_processor()

    def _start_queue_processor(self) -> None:
        """Start the click queue processor thread"""
        if self.queue_processor_thread and self.queue_processor_thread.is_alive():
            return

        self.queue_processor_thread = threading.Thread(
            target=self._process_click_queue,
            daemon=True,
            name="ClickQueueProcessor"
        )
        self.queue_processor_thread.start()

    def _stop_queue_processor(self) -> None:
        """Stop the click queue processor thread"""
        if self.queue_processor_thread:
            self.click_queue.append(None)  # Sentinel value to stop processor
            self.queue_processor_thread.join(timeout=1.0)
            self.queue_processor_thread = None

    def _process_click_queue(self) -> None:
        """Process clicks from the queue"""
        while True:
            try:
                click_data = self.click_queue.popleft()
                if click_data is None:  # Sentinel value
                    break

                x, y, mouse_button, click_type = click_data
                self._perform_click(x, y, mouse_button, click_type)

            except IndexError:
                # Queue is empty, wait a bit
                time.sleep(0.001)
            except Exception as e:
                print(f"Queue processor error: {e}")

    def stop_clicking(self) -> None:
        """Stop the clicking process"""
        self.is_running = False
        self._stop_event.set()

        # Stop queue processor
        self._stop_queue_processor()

        # Wait for thread to finish
        if self.click_thread and self.click_thread.is_alive():
            self.click_thread.join(timeout=1.0)

        self.click_thread = None

    def emergency_stop(self) -> None:
        """Emergency stop - immediate halt"""
        self.is_running = False
        self._stop_event.set()

    def _click_loop(self, x: int, y: int, interval: float, variation: int,
                   burst_clicks: int, burst_pause: float, max_clicks: int,
                   auto_stop_minutes: int, mouse_button: str, click_type: str,
                   on_click_complete: Optional[Callable],
                   on_status_update: Optional[Callable]) -> None:
        """Main clicking loop"""
        try:
            while self.is_running and not self._stop_event.is_set():
                # Check auto-stop conditions
                if self._should_stop(max_clicks, auto_stop_minutes):
                    break

                # Perform clicks
                self._perform_burst(x, y, burst_clicks, burst_pause,
                                  mouse_button, click_type)

                # Wait for next burst
                if self.is_running and not self._stop_event.is_set():
                    self._wait_with_variation(interval, variation)

            # Call completion callback
            if on_click_complete:
                on_click_complete()

        except Exception as e:
            print(f"Click loop error: {e}")
            if on_click_complete:
                on_click_complete()

    def _should_stop(self, max_clicks: int, auto_stop_minutes: int) -> bool:
        """Check if clicking should stop based on limits"""
        # Check click limit
        if max_clicks > 0 and self.click_count >= max_clicks:
            return True

        # Check time limit
        if auto_stop_minutes > 0:
            elapsed_minutes = (time.time() - self.start_time) / 60
            if elapsed_minutes >= auto_stop_minutes:
                return True

        return False

    def _perform_burst(self, x: int, y: int, burst_clicks: int, burst_pause: float,
                      mouse_button: str, click_type: str) -> None:
        """Perform a burst of clicks"""
        for i in range(burst_clicks):
            if not self.is_running or self._stop_event.is_set():
                break

            self._perform_click(x, y, mouse_button, click_type)
            self.click_count += 1

            # Wait between clicks in burst (except for last click)
            if burst_clicks > 1 and i < burst_clicks - 1:
                time.sleep(burst_pause)

    def _perform_click(self, x: int, y: int, mouse_button: str, click_type: str) -> None:
        """Perform a single click at coordinates with performance monitoring"""
        click_start_time = time.perf_counter() if self.enable_performance_monitoring else None

        try:
            # Check if queuing is enabled and queue is not full
            if self.enable_queuing and len(self.click_queue) < self.max_queue_size:
                # Add click to queue instead of executing immediately
                self.click_queue.append((x, y, mouse_button, click_type))
                return

            # Validate coordinates
            screen_width, screen_height = pyautogui.size()
            if not (0 <= x <= screen_width and 0 <= y <= screen_height):
                raise CoordinateError(x, y, f"Coordinates ({x}, {y}) are outside screen bounds ({screen_width}x{screen_height})")

            # Move to position with optimized timing
            move_start = time.perf_counter()
            pyautogui.moveTo(x, y, duration=0.01)
            move_time = time.perf_counter() - move_start

            # Perform click based on button and type
            try:
                click_operation_start = time.perf_counter()
                if mouse_button == 'left':
                    if click_type == 'double':
                        pyautogui.doubleClick()
                    else:
                        pyautogui.click()
                elif mouse_button == 'right':
                    pyautogui.rightClick()
                elif mouse_button == 'middle':
                    pyautogui.middleClick()
                else:
                    raise ClickEngineError("perform_click", f"Unsupported mouse button: {mouse_button}")
                click_operation_time = time.perf_counter() - click_operation_start

                # Record performance metrics
                if self.enable_performance_monitoring:
                    total_time = time.perf_counter() - click_start_time
                    self.performance_metrics['click_timings'].append(total_time)
                    self.performance_metrics['click_success_count'] += 1
                    self.performance_metrics['total_click_time'] += total_time
                    self.performance_metrics['min_click_time'] = min(self.performance_metrics['min_click_time'], total_time)
                    self.performance_metrics['max_click_time'] = max(self.performance_metrics['max_click_time'], total_time)

            except pyautogui.FailSafeException:
                if self.enable_performance_monitoring:
                    self.performance_metrics['click_error_count'] += 1
                raise SafetyError("fail_safe", "detected", "User moved mouse to corner during operation")
            except pyautogui.PyAutoGUIException as e:
                if self.enable_performance_monitoring:
                    self.performance_metrics['click_error_count'] += 1
                raise ClickEngineError("perform_click", f"PyAutoGUI error: {e}")

        except (CoordinateError, ClickEngineError, SafetyError):
            # Record error metrics
            if self.enable_performance_monitoring:
                self.performance_metrics['click_error_count'] += 1
            # Re-raise our custom exceptions
            raise
        except Exception as e:
            # Record error metrics for unexpected errors
            if self.enable_performance_monitoring:
                self.performance_metrics['click_error_count'] += 1
            # Wrap unexpected errors
            raise ClickEngineError("perform_click", f"Unexpected error: {e}") from e

    def _wait_with_variation(self, interval: float, variation: int) -> None:
        """Wait for the specified interval with random variation"""
        if variation > 0:
            actual_interval = interval + random.randint(-variation, variation)
        else:
            actual_interval = interval

        # Convert to seconds and ensure minimum
        wait_time = max(actual_interval / 1000, 0.001)
        time.sleep(wait_time)

    def get_status(self) -> dict:
        """Get current clicking status"""
        elapsed = int(time.time() - self.start_time) if self.start_time > 0 else 0
        hours = elapsed // 3600
        minutes = (elapsed % 3600) // 60
        seconds = elapsed % 60

        status = {
            'is_running': self.is_running,
            'click_count': self.click_count,
            'runtime': f"{hours:02d}:{minutes:02d}:{seconds:02d}",
            'thread_alive': self.click_thread.is_alive() if self.click_thread else False,
            'queue_size': len(self.click_queue),
            'enable_queuing': self.enable_queuing
        }

        # Add performance metrics if enabled
        if self.enable_performance_monitoring:
            metrics = self.get_performance_metrics()
            status['performance'] = {
                'clicks_per_second': round(metrics.get('clicks_per_second', 0), 2),
                'success_rate': round(metrics.get('success_rate', 0), 1),
                'average_click_time': round(metrics.get('average_click_time', 0) * 1000, 2),  # Convert to ms
                'total_errors': metrics.get('click_error_count', 0)
            }

        return status
