import csv
import traceback
from enum import Enum
from pathlib import Path
from typing import Iterable, List

import cv2
import numpy as np

from topping_bot.optimize.toppings import INFO, Resonance, Topping
from topping_bot.util.const import DEBUG_PATH, STATIC_PATH

RESONANCE_THRESHOLD = 0.3
KERNEL = np.ones((2, 2), np.uint8)
READER_PATH = STATIC_PATH / "reader"
TEMPLATES = {
    "flavor": {fp: cv2.imread(str(fp), cv2.IMREAD_GRAYSCALE) for fp in (READER_PATH / "flavor").iterdir()},
    "substat": {fp: cv2.imread(str(fp), cv2.IMREAD_GRAYSCALE) for fp in (READER_PATH / "substat").iterdir()},
    "digits": {fp: cv2.imread(str(fp), cv2.IMREAD_GRAYSCALE) for fp in (READER_PATH / "digits").iterdir()},
    "resonant": {fp.stem: cv2.imread(str(fp), cv2.IMREAD_GRAYSCALE) for fp in (READER_PATH / "resonant").iterdir()},
    "resonant_indicator": cv2.imread(str(READER_PATH / "resonant" / "resonant_indicator_bw.png"), cv2.IMREAD_GRAYSCALE),
}


def nothing(x):
    pass


def roi_selector(input_frame):
    # Create a window and trackbars to adjust the region of interest
    cv2.namedWindow("ROI Selector", cv2.WINDOW_NORMAL)
    cv2.resizeWindow("ROI Selector", 800, 600)
    cv2.createTrackbar("Offset X", "ROI Selector", 0, input_frame.shape[1], nothing)
    cv2.createTrackbar("Offset Y", "ROI Selector", 0, input_frame.shape[0], nothing)
    cv2.createTrackbar("Width", "ROI Selector", 100, input_frame.shape[1], nothing)
    cv2.createTrackbar("Height", "ROI Selector", 100, input_frame.shape[0], nothing)

    while True:
        # Get current positions of trackbars
        offset_x = cv2.getTrackbarPos("Offset X", "ROI Selector")
        offset_y = cv2.getTrackbarPos("Offset Y", "ROI Selector")
        width = cv2.getTrackbarPos("Width", "ROI Selector")
        height = cv2.getTrackbarPos("Height", "ROI Selector")

        # Draw the ROI on the frame
        display_frame = input_frame.copy()
        cv2.rectangle(display_frame, (offset_x, offset_y), (offset_x + width, offset_y + height), (0, 255, 0), 2)
        cv2.imshow("ROI Selector", display_frame)

        # Wait for the 'q' key to quit
        if cv2.waitKey(1) & 0xFF == ord("q"):
            break

    cv2.destroyAllWindows()
    return offset_x, offset_y, width, height


def read_toppings(fp: Path) -> List[Topping]:
    toppings = []
    with open(fp) as f:
        reader = csv.reader(f)
        for row in reader:
            toppings.append(Topping([eval(substat) for substat in row[1:-1]], resonance=Resonance(row[-1])))
    return toppings


def write_toppings(toppings: Iterable[Topping], fp: Path, append=False):
    mode = "w" if not append else "a"
    with open(fp, mode=mode, newline="") as f:
        writer = csv.writer(f)
        for topping in toppings:
            writer.writerow(
                [topping.flavor.value]
                + [(substat.value, str(value)) for substat, value in topping.substats]
                + [topping.resonance.value]
            )


def image_diff(source: np.ndarray, template: np.ndarray, top_left, bot_right, debug=False):
    h, w = template.shape

    result = cv2.matchTemplate(source, template, cv2.TM_SQDIFF)
    min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)
    x, y = min_loc

    if abs(top_left[0] - y) > 10 or abs(bot_right[0] - (y + h)) > 10:
        return float("inf")
    if abs(top_left[1] - x) > 15 or abs(bot_right[1] - (x + w)) > 25:
        return float("inf")

    return cv2.norm(source[y : y + h, x : x + w], template)


def image_to_substat(source: np.ndarray, template, debug=False):
    active_pixels = np.stack(np.where(source == 0))
    if active_pixels.size == 0:
        return None

    top_left = np.min(active_pixels, axis=1).astype(np.int32)
    bot_right = np.max(active_pixels, axis=1).astype(np.int32)

    return fp_to_type(
        min(TEMPLATES[template], key=lambda x: image_diff(source, TEMPLATES[template][x], top_left, bot_right, debug))
    )


def image_to_decimal(source: np.ndarray):
    y, x = source.shape

    if cv2.countNonZero(source) == y * x:
        return None

    source = cv2.dilate(source, KERNEL)

    contours, hierarchies = cv2.findContours(source, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
    # rectangles = [cv2.boundingRect(c) for c in contours if y * x * 0.025 < cv2.contourArea(c) < y * x * 0.9]

    rectangles = [cv2.boundingRect(c) for c in contours if y * x * 0.01 < cv2.contourArea(c) < y * x * 0.9]

    rectangles += rectangles
    rectangles, weights = cv2.groupRectangles(rectangles, 1, eps=0.5)

    digits = sorted(rectangles, key=lambda z: z[0])[:-1]  # ignore % sign
    digits = [source[y : y + h, x : x + w] for x, y, w, h in digits]

    digits = [min(TEMPLATES["digits"], key=lambda z: diff(digit, TEMPLATES["digits"][z])).stem for digit in digits]

    if 0 < len(digits) <= 2:
        return ".".join(digits)
    return "0"


def fp_to_type(fp: Path):
    stem = fp.stem
    for substat, info in INFO.items():
        if stem == info["filename"]:
            return substat


def fp_to_value(fp: Path):
    stem = fp.stem
    return stem.replace("_", ".")


def diff(source: np.ndarray, template: np.ndarray):
    source = cv2.resize(source, template.shape[::-1])
    return cv2.norm(source, template)


def detect_blur(image, size=60, thresh=10):
    (h, w) = image.shape
    (cX, cY) = (int(w / 2.0), int(h / 2.0))

    fft = np.fft.fft2(image)
    fft_shift = np.fft.fftshift(fft)
    fft_shift[cY - size : cY + size, cX - size : cX + size] = 0
    fft_shift = np.fft.ifftshift(fft_shift)
    recon = np.fft.ifft2(fft_shift)

    magnitude = 20 * np.log(np.abs(recon))
    mean = np.mean(magnitude)

    return mean <= thresh


def extract_unique_frames(fp: Path):
    video = cv2.VideoCapture(str(fp))
    for _ in range(2):
        success, frame = video.read()
    is_video = success

    video = cv2.VideoCapture(str(fp))

    last_partial_frame = None
    success, frame = video.read()
    y, x, c = frame.shape
    while success:
        if not is_video:
            yield frame, is_video
            return

        # crop left half
        frame = frame[:, : x // 2]
        partial_frame = frame[y // 2 : -(y // 4)]

        # will have to be revisited, this bugs out
        # if detect_blur(cv2.cvtColor(partial_frame, cv2.COLOR_BGR2GRAY), thresh=10):
        #     continue

        # unique frame check
        if last_partial_frame is None:
            new_y, new_x, new_c = partial_frame.shape
            threshold = new_y * new_x // 200
            last_partial_frame = partial_frame
            yield frame, is_video
        elif cv2.norm(last_partial_frame, partial_frame, cv2.NORM_L2) > threshold:
            last_partial_frame = partial_frame
            yield frame, is_video
        success, frame = video.read()

    video.release()


def extract_topping_data(unique_frames: Iterable[np.ndarray], debug=False, verbose=False):
    cv2.destroyAllWindows()

    last_topping = None
    bounding_rectangle = None
    for i, (frame, is_video) in enumerate(unique_frames):
        if not is_video and (result := extract_multiupgrade_topping_data(frame)) is not None:
            yield result
            return
        elif not is_video:
            y, x, c = frame.shape
            frame = frame[:, : x // 2]

        if last_topping is None:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            threshold = cv2.threshold(gray, 215, 255, cv2.THRESH_BINARY)[1]

            contours, hierarchies = cv2.findContours(threshold, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
            if not contours:
                continue
            contour = max(contours, key=lambda x: cv2.contourArea(x))

            if cv2.contourArea(contour) <= 10_000:
                continue
            bounding_rectangle = cv2.boundingRect(contour)

        x, y, w, h = bounding_rectangle
        frame = frame[y : y + h, x : x + w]

        y, x, c = frame.shape
        scale_factor = 1400 / y
        frame = cv2.resize(frame, None, fx=scale_factor, fy=scale_factor, interpolation=cv2.INTER_CUBIC)

        y, x, c = frame.shape
        if x < 1780:
            continue

        frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        threshold, frame = cv2.threshold(frame, 180, 255, cv2.THRESH_BINARY)

        topping_info = frame[750:1220, 140:]

        main = frame[740:847]
        flavor, value = image_to_substat(main[:, :1430], "flavor"), image_to_decimal(main[:, 1430:])
        if flavor is None or value is None or value == "0":
            continue

        substats = [(flavor, value)]
        substats_info = topping_info[140:]

        for j in range(3):
            line = substats_info[125 * j : 125 * j + 80]
            substat, value = image_to_substat(line[:, 10:1345], "substat"), image_to_decimal(line[:, 1345:])

            if substat is None or value is None:
                continue

            substats.append((substat, value))

        # Resonance check
        if substats:
            resonant_indicator_roi = frame[235:315, 1070:1160]

            h, w = resonant_indicator_roi.shape
            if np.count_nonzero(resonant_indicator_roi == 0) / (h * w) < 0.5:
                metatype = Resonance.NORMAL
            else:
                # metatype check
                title = frame[100:225, 200:-200]

                active_pixels = np.stack(np.where(title == 0))
                if active_pixels.size == 0:
                    return None

                # to capture new resonance template
                # cv2.imwrite(str(READER_PATH / "resonant" / "new.jpg"), title)

                metatype = None
                metatype_error = float("inf")
                for resonance in [resonance for resonance in Resonance if resonance != Resonance.NORMAL]:
                    template = TEMPLATES["resonant"][resonance.value.lower().replace(" ", "_")]
                    h, w = template.shape

                    result = cv2.matchTemplate(title, template, cv2.TM_SQDIFF)
                    min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)

                    x, y = min_loc

                    if (error := cv2.norm(title[y : y + h, x : x + w], template, cv2.NORM_L1) / (h * w)) < metatype_error:
                        metatype = resonance
                        metatype_error = error

            topping = Topping(substats, resonance=metatype)
            if not topping.validate():
                continue
            elif last_topping is None or topping != last_topping:
                last_topping = topping
                yield topping


def extract_multiupgrade_topping_data(frame: np.ndarray):
    y, x, c = frame.shape
    frame = frame[:, x // 2 :]

    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    threshold = cv2.threshold(gray, 215, 255, cv2.THRESH_BINARY)[1]

    contours, hierarchies = cv2.findContours(threshold, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return
    contour = max(contours, key=lambda x: cv2.contourArea(x))

    if cv2.contourArea(contour) <= 10_000:
        return
    bounding_rectangle = cv2.boundingRect(contour)

    x, y, w, h = bounding_rectangle
    frame = frame[y: y + h, x: x + w]

    y, x, c = frame.shape
    scale_factor = 1400 / y
    frame = cv2.resize(frame, None, fx=scale_factor, fy=scale_factor, interpolation=cv2.INTER_CUBIC)

    y, x, c = frame.shape
    if x < 1780:
        return

    frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    threshold, info_frame = cv2.threshold(frame, 180, 255, cv2.THRESH_BINARY)

    topping_info = info_frame[833:1340, 50:-50]
    main = topping_info[13:120]
    scale_factor = 65 / 53
    main = cv2.resize(main, None, fx=scale_factor, fy=scale_factor, interpolation=cv2.INTER_CUBIC)

    flavor, value = image_to_substat(main[:, :1430], "flavor"), image_to_decimal(main[:, 1430:])
    if flavor is None or value is None or value == "0":
        return
    substats = [(flavor, value)]
    substats_info = topping_info[176:]

    for j in range(3):
        line = substats_info[114 * j: 114 * j + 80]
        substat, value = image_to_substat(line[:, 100:1345], "substat"), image_to_decimal(line[:, 1345:])

        if substat is None or value is None:
            continue

        substats.append((substat, value))

    threshold, info_frame = cv2.threshold(frame, 150, 255, cv2.THRESH_BINARY)
    res_info = info_frame[608:708, 200:-200]
    scale_factor = 73 / 63
    res_info = cv2.resize(res_info, None, fx=scale_factor, fy=scale_factor, interpolation=cv2.INTER_CUBIC)

    active_pixels = np.stack(np.where(res_info == 0))
    if active_pixels.size == 0:
        return
    top_left = np.min(active_pixels, axis=1).astype(np.int32)

    metatype = Resonance.NORMAL
    for resonance in [resonance for resonance in Resonance if resonance != Resonance.NORMAL]:
        template = TEMPLATES["resonant"][resonance.value.lower().replace(" ", "_")]
        h, w = template.shape

        result = cv2.matchTemplate(res_info, template, cv2.TM_SQDIFF)
        min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)

        x, y = min_loc
        if abs(top_left[0] - y) > 10 or (abs(top_left[1] - x) > 15 and resonance != Resonance.TRIO):
            continue

        if cv2.norm(res_info[y: y + h, x: x + w], template, cv2.NORM_L1) / (h * w) < 25:  # TODO Dial In Const
            metatype = resonance
            break

    topping = Topping(substats, resonance=metatype)
    if not topping.validate():
        return
    return topping
