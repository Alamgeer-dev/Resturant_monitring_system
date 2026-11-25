"""Find working cameras and show a preview.

Usage: python scripts/check_camera.py
"""
import cv2


def main():
    found = []
    for i in range(8):
        cap = cv2.VideoCapture(i)
        if cap.isOpened():
            ok, frame = cap.read()
            w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            print(f"[OK] camera index {i}: {w}x{h}, frame={ok}")
            found.append(i)
            if ok:
                cv2.imshow(f"Camera {i} - press any key", frame)
                cv2.waitKey(1500)
                cv2.destroyAllWindows()
        cap.release()
    print("Working indices:", found if found else "none")


if __name__ == "__main__":
    main()
