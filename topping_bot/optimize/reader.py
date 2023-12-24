import csv
from enum import Enum
from pathlib import Path
from typing import Iterable, List

import cv2
import numpy as np

from topping_bot.crk.toppings import INFO, Resonance, Topping
from topping_bot.util.const import DEBUG_PATH, STATIC_PATH

KERNEL = np.ones((2, 2), np.uint8)
READER_PATH = STATIC_PATH / "reader"
TEMPLATES = {
    "flavor": {fp: cv2.imread(str(fp), cv2.IMREAD_GRAYSCALE) for fp in (READER_PATH / "flavor").iterdir()},
    "substat": {fp: cv2.imread(str(fp), cv2.IMREAD_GRAYSCALE) for fp in (READER_PATH / "substat").iterdir()},
    "digits": {fp: cv2.imread(str(fp), cv2.IMREAD_GRAYSCALE) for fp in (READER_PATH / "digits").iterdir()},
    "resonant": {fp.stem: cv2.imread(str(fp), cv2.IMREAD_GRAYSCALE) for fp in (READER_PATH / "resonant").iterdir()},
    "resonant_indicator": cv2.imread(str(READER_PATH / "resonant" / "resonant_indicator_bw.png"), cv2.IMREAD_GRAYSCALE)
}

class STATE(Enum):
    WAITING = "Waiting"
    STARTED = "Started"
    ENDED = "Ended"


def read_toppings(fp: Path):
    toppings = []
    with open(fp) as f:
        reader = csv.reader(f)
        for row in reader:
            toppings.append(Topping([eval(substat) for substat in row[1:-1]], resonance=Resonance(row[-1])))
    return toppings


def write_toppings(toppings: List[Topping], fp: Path, append=False):
    mode = "w" if not append else "a"
    with open(fp, mode, newline="") as f:
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


def extract_unique_frames(fp: Path):
    video = cv2.VideoCapture(str(fp))
    for _ in range(2):
        success, frame = video.read()
    is_video = success

    video = cv2.VideoCapture(str(fp))

    count = -1
    last_partial_frame = None
    success, frame = video.read()
    y, x, c = frame.shape
    while success:
        if is_video and count < 6:
            success, frame = video.read()
            count += 1
            continue

        # crop left half
        frame = frame[:, : x // 2]
        partial_frame = frame[y // 2 : -(y // 4)]

        # unique frame check
        if last_partial_frame is None:
            new_y, new_x, new_c = partial_frame.shape
            threshold = new_y * new_x // 200
            last_partial_frame = partial_frame
            yield frame
        elif cv2.norm(last_partial_frame, partial_frame, cv2.NORM_L2) > threshold:
            last_partial_frame = partial_frame
            yield frame
        success, frame = video.read()

    video.release()


current_min = 0
def extract_topping_data(unique_frames: Iterable[np.ndarray], debug=False, verbose=False):
    global current_min
    cv2.destroyAllWindows()

    state = STATE.WAITING
    last_topping = None
    bounding_rectangle = None
    for i, frame in enumerate(unique_frames):
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
            # MIN threshold found for max_val over 300 resonant toppings: 0.3076988756656647, std deviation of 0.4931
            # MAX threshold found for max_val over 300 normal toppings: 0.2755431830883026, std deviation of 0.0004
            # Determined that 0.3 should never be exceeded by normal toppings, and should always be exceeded by resonant toppings
            RESONANCE_THRESHOLD = 0.3
            
            resonant_indicator_roi = frame[235:315, 1070:1160]
            match = cv2.matchTemplate(resonant_indicator_roi, TEMPLATES["resonant_indicator"], cv2.TM_CCOEFF_NORMED)
            _, max_val, _, _ = cv2.minMaxLoc(match)
            
            if max_val < RESONANCE_THRESHOLD:
                metatype = Resonance.NORMAL
            else:
                # metatype check
                title = frame[100:225, 200:-200]

                active_pixels = np.stack(np.where(title == 0))
                if active_pixels.size == 0:
                    return None

                top_left = np.min(active_pixels, axis=1).astype(np.int32)

                # to capture new resonance template
                # cv2.imwrite(str(READER_PATH / "resonant" / "new.jpg"), title)

                metatype = Resonance.NORMAL
                # print("RESONANCE CHECK")
                for resonance in [resonance for resonance in Resonance if resonance != Resonance.NORMAL]:
                    template = TEMPLATES["resonant"][resonance.value.lower().replace(" ", "_")]
                    h, w = template.shape

                    result = cv2.matchTemplate(title, template, cv2.TM_SQDIFF)
                    min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)

                    x, y = min_loc
                    # print(resonance, "Cont", abs(top_left[0] - y) > 10 or abs(top_left[1] - x) > 15, cv2.norm(title[y : y + h, x : x + w], template), h * w * 0.65)
                    if abs(top_left[0] - y) > 10 or abs(top_left[1] - x) > 15 and resonance != Resonance.TRIO:
                        continue

                    # if resonance == Resonance.SEA_SALT:
                    #     tmp = cv2.cvtColor(title, cv2.COLOR_GRAY2BGR)
                    #     tmp = cv2.rectangle(tmp, (x, y), (x + w, y + h), (255, 0, 0), 2)
                    #     cv2.imshow("Dev", tmp)
                    #     cv2.waitKey(0)

                    if cv2.norm(title[y : y + h, x : x + w], template) < h * w * 0.6:
                        metatype = resonance
                        break

            topping = Topping(substats, resonance=metatype)
            if not topping.validate():
                if state == STATE.STARTED:
                    if verbose:
                        cv2.imwrite(str(DEBUG_PATH / f"{i}.png"), frame)
                        with open(DEBUG_PATH / f"{i}.txt", "w") as f:
                            f.write("VERBOSE\n")
                            f.write(f"{substats}\n")
                    if not debug:
                        state = STATE.ENDED
                elif state == STATE.WAITING or STATE.ENDED:
                    continue
            elif last_topping is None or topping != last_topping:
                if state == STATE.ENDED:
                    if debug:
                        ...
                    else:
                        raise ValueError
                else:
                    state = STATE.STARTED
                    last_topping = topping
                    yield topping
        elif last_topping:
            return
