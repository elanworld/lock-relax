from unittest.mock import patch
import lock_relax
import time

def test_api():
        with patch("lock_relax.show_countdown_warning") as mock_func_show_countdown_warning, \
             patch("lock_relax.lock_screen") as mock_func_lock_screen, \
                patch("time.sleep", return_value=None) as mock_sleep:
            print("This is a test function.")
            mock_func_lock_screen.side_effect = lambda *args, **kwargs: print(f"Mocked lock_screen called with args: {args}, kwargs: {kwargs}")
            mock_func_show_countdown_warning.side_effect = lambda *args, **kwargs: print(f"Mocked show_countdown_warning called with args: {args}, kwargs: {kwargs}")
            mock_sleep.side_effect = lambda *args, **kwargs: print(f"Mocked sleep called with args: {args}, kwargs: {kwargs}") if args[0] > 10 else None

            lock_relax.main()