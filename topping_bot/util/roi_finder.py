import cv2
from pathlib import Path

def nothing(x):
    pass

def roi_selector(input_frame, topping_debug=False):
    # Apply the same preprocessing as in /static/reader/reader.py
    if topping_debug:
        input_frame = input_frame[:, :input_frame.shape[1] // 2]
        scale_factor = 1400 / input_frame.shape[0]
        input_frame = cv2.resize(input_frame, None, fx=scale_factor, fy=scale_factor, interpolation=cv2.INTER_CUBIC)
        input_frame = cv2.cvtColor(input_frame, cv2.COLOR_BGR2GRAY)
        _, input_frame = cv2.threshold(input_frame, 180, 255, cv2.THRESH_BINARY)

    # Create a window and trackbars to adjust the region of interest
    cv2.namedWindow('ROI Selector', cv2.WINDOW_NORMAL)
    cv2.resizeWindow('ROI Selector', 800, 600)
    cv2.createTrackbar('Offset X', 'ROI Selector', 0, input_frame.shape[1], nothing)
    cv2.createTrackbar('Offset Y', 'ROI Selector', 0, input_frame.shape[0], nothing)
    cv2.createTrackbar('Width', 'ROI Selector', 100, input_frame.shape[1], nothing)
    cv2.createTrackbar('Height', 'ROI Selector', 100, input_frame.shape[0], nothing)

    while True:
        # Get current positions of trackbars
        offset_x = cv2.getTrackbarPos('Offset X', 'ROI Selector')
        offset_y = cv2.getTrackbarPos('Offset Y', 'ROI Selector')
        width = cv2.getTrackbarPos('Width', 'ROI Selector')
        height = cv2.getTrackbarPos('Height', 'ROI Selector')

        # Draw the ROI on the frame
        display_frame = input_frame.copy()
        cv2.rectangle(display_frame, (offset_x, offset_y), (offset_x + width, offset_y + height), (0, 255, 0), 2)
        cv2.imshow('ROI Selector', display_frame)

        # Wait for the 'q' key to quit
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cv2.destroyAllWindows()
    return offset_x, offset_y, width, height

# Example usage

# TOPPING_DEBUG = False
# example_frame_path = "path/to/your/test/frame.png"  # replace with your actual frame path
# frame = cv2.imread(example_frame_path)
# roi = roi_selector(frame, TOPPING_DEBUG)
# print(f"Selected ROI: {roi}")
