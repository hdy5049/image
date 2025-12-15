import sys
import cv2
import easyocr
import numpy as np
import platform
import os
import time  # QTimer의 최소 시간 간격을 설정하기 위해 사용

# Pillow (PIL) 라이브러리 import
from PIL import Image, ImageDraw, ImageFont

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget,
    QPushButton, QLabel, QFileDialog,
    QVBoxLayout, QHBoxLayout, QMessageBox, QSizePolicy
)
from PyQt5.QtGui import QImage, QPixmap, QFont
from PyQt5.QtCore import Qt, QSize, QTimer  # QTimer 추가

# ======================
# [설정] 한글 폰트 경로 설정 (Windows 환경 기준)
# ======================
if platform.system() == 'Windows':
    FONT_PATH = "C:/Windows/Fonts/malgun.ttf"
elif platform.system() == 'Darwin':
    FONT_PATH = "/System/Library/Fonts/Supplemental/AppleGothic.ttf"
else:
    FONT_PATH = "/usr/share/fonts/truetype/nanum/NanumGothic.ttf"

if not os.path.exists(FONT_PATH):
    print(f"경고: 설정된 폰트 경로({FONT_PATH})를 찾을 수 없습니다. 기본 폰트를 사용합니다.")

# ======================
# OCR 초기화
# ======================
try:
    reader = easyocr.Reader(['ko', 'en'], gpu=False)
except Exception as e:
    print(f"EasyOCR 초기화 실패: {e}")
    reader = None


# ======================
# PIL을 이용한 한글 출력 함수 (cv2.putText 대체)
# ======================
def put_korean_text(img, text, pos, font_path, font_size, color=(0, 255, 0)):
    # OpenCV 이미지를 PIL 이미지로 변환
    img_pil = Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
    draw = ImageDraw.Draw(img_pil)

    # 폰트 로드
    try:
        font = ImageFont.truetype(font_path, font_size)
    except IOError:
        font = ImageFont.load_default()

    # 텍스트 출력
    rgb_color = (color[2], color[1], color[0])
    draw.text(pos, text, font=font, fill=rgb_color)

    # PIL 이미지를 다시 OpenCV 이미지로 변환
    return cv2.cvtColor(np.array(img_pil), cv2.COLOR_RGB2BGR)


# ======================
# OCR 처리 함수
# ======================
def process_frame(frame):
    if frame is None or reader is None:
        return None, "EasyOCR 로드 오류"

    vis_results = reader.readtext(frame, detail=1, paragraph=False)

    vis_frame = frame.copy()
    recognized_texts = []

    for (bbox, text, conf) in vis_results:
        recognized_texts.append(text)
        pts = np.array(bbox, dtype=np.int32)

        # 1. 박스 그리기
        cv2.polylines(vis_frame, [pts], True, (255, 165, 0), 2)  # 주황색 박스

        # 2. 한글 출력 (PIL 함수 사용)
        vis_frame = put_korean_text(
            vis_frame,
            text,
            (pts[0][0], pts[0][1] - 30),
            FONT_PATH,
            font_size=24,
            color=(0, 255, 0)
        )

    full_text = ' '.join(recognized_texts)
    # print(f"--- OCR 결과 ---: {full_text}") # 동영상 처리 시 너무 자주 출력될 수 있으므로 주석 처리

    return vis_frame, full_text


# ======================
# 메인 윈도우 (동영상 기능 추가)
# ======================
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        # 동영상 관련 변수 초기화
        self.cap = None  # cv2.VideoCapture 객체
        self.timer = QTimer(self)  # QTimer 객체
        self.timer.timeout.connect(self.update_frame)  # 타이머 연결

        self.setWindowTitle("차량 번호판 OCR 분석기 (이미지/동영상)")
        self.setGeometry(100, 100, 1000, 750)
        self.setStyleSheet(self.get_stylesheet())

        central = QWidget()
        self.setCentralWidget(central)

        self.label = QLabel("이미지 또는 동영상을 불러오세요.")
        self.label.setObjectName("ImageLabel")
        self.label.setAlignment(Qt.AlignCenter)
        self.label.setMinimumSize(850, 550)
        self.label.setStyleSheet(
            "#ImageLabel { background-color: #212121; color: #E0E0E0; border: 2px solid #555555; border-radius: 8px; font-size: 18px; }"
        )
        self.label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        self.result_label = QLabel("인식된 번호판 텍스트:")
        self.result_label.setFont(QFont("Malgun Gothic", 12))
        self.result_label.setStyleSheet("color: #FFC107; padding: 5px;")

        # 버튼 추가
        self.btn_image = QPushButton("📸 이미지 열기")
        self.btn_image.setObjectName("ImageButton")
        self.btn_image.clicked.connect(self.open_image)

        self.btn_video = QPushButton("▶️ 동영상 열기")  # 동영상 버튼 추가
        self.btn_video.setObjectName("VideoButton")
        self.btn_video.clicked.connect(self.open_video)

        self.btn_exit = QPushButton("🚪 종료")
        self.btn_exit.setObjectName("ExitButton")
        self.btn_exit.clicked.connect(self.close)

        btn_layout = QHBoxLayout()
        btn_layout.addWidget(self.btn_image)
        btn_layout.addWidget(self.btn_video)  # 버튼 레이아웃에 추가
        btn_layout.addStretch(1)
        btn_layout.addWidget(self.btn_exit)

        main_layout = QVBoxLayout()
        main_layout.addWidget(self.result_label)
        main_layout.addWidget(self.label)
        main_layout.addLayout(btn_layout)

        central.setLayout(main_layout)

    def get_stylesheet(self):
        return """
            QMainWindow {
                background-color: #1E1E1E;
            }
            QWidget {
                background-color: #1E1E1E;
                color: #E0E0E0;
            }
            QPushButton {
                background-color: #4CAF50; 
                color: white;
                border: none;
                padding: 10px 20px;
                border-radius: 5px;
                font-size: 16px;
                min-width: 150px;
            }
            QPushButton:hover {
                background-color: #66BB6A;
            }
            #VideoButton {
                background-color: #2196F3; /* 동영상 버튼 파란색 */
            }
            #VideoButton:hover {
                background-color: #64B5F6;
            }
            #ExitButton {
                background-color: #F44336;
            }
            #ExitButton:hover {
                background-color: #E57373;
            }
        """

    # ======================
    # 이미지 열기 (기존 함수)
    # ======================
    def open_image(self):
        # 동영상 재생 중지
        self.stop_video()

        path, _ = QFileDialog.getOpenFileName(
            self, "차량 번호판 이미지 선택", "", "Images (*.png *.jpg *.jpeg *.webp)"
        )

        if not path:
            return

        img = cv2.imread(path)
        if img is None:
            QMessageBox.warning(self, "오류", "이미지를 불러올 수 없습니다. 경로를 확인하세요.")
            return

        result_frame, recognized_text = process_frame(img)

        self.update_result_label(recognized_text)

        if result_frame is not None:
            self.show_frame(result_frame)

    # ======================
    # 동영상 열기 (추가된 기능)
    # ======================
    def open_video(self):
        self.stop_video()

        path, _ = QFileDialog.getOpenFileName(
            self, "동영상 파일 선택", "", "Video Files (*.mp4 *.avi *.mov *.mkv)"
        )

        if not path:
            return

        self.cap = cv2.VideoCapture(path)
        if not self.cap.isOpened():
            QMessageBox.warning(self, "오류", "동영상 파일을 열 수 없습니다.")
            return

        # 동영상의 FPS를 기반으로 타이머 간격 설정 (30FPS 기준 33ms)
        fps = self.cap.get(cv2.CAP_PROP_FPS)
        if fps > 0:
            delay = int(1000 / fps)
        else:
            delay = 33  # 기본 30FPS (33ms)

        self.timer.start(delay)
        self.result_label.setText("인식된 번호판 텍스트: <span style='color: #4CAF50;'>동영상 재생 중...</span>")

    # ======================
    # 동영상 프레임 업데이트 (추가된 기능)
    # ======================
    def update_frame(self):
        if self.cap is None:
            self.stop_video()
            return

        ret, frame = self.cap.read()

        if ret:
            # 프레임당 OCR 처리
            result_frame, recognized_text = process_frame(frame)

            # 인식된 텍스트를 UI에 표시 (빈 문자열이 아닐 경우만 업데이트)
            if recognized_text:
                self.update_result_label(recognized_text)

            if result_frame is not None:
                self.show_frame(result_frame)
        else:
            # 동영상 끝에 도달
            self.stop_video()
            QMessageBox.information(self, "정보", "동영상 재생이 완료되었습니다.")

    # ======================
    # 동영상 재생 중지 (추가된 기능)
    # ======================
    def stop_video(self):
        if self.timer.isActive():
            self.timer.stop()
        if self.cap is not None:
            self.cap.release()
            self.cap = None

    # ======================
    # 결과 레이블 업데이트 도우미 함수
    # ======================
    def update_result_label(self, text):
        if text and text != "EasyOCR 로드 오류":
            self.result_label.setText(
                f"인식된 번호판 텍스트: <span style='font-weight: bold; color: #4CAF50;'>{text}</span>")
        else:
            self.result_label.setText(
                "인식된 번호판 텍스트: <span style='font-weight: bold; color: #F44336;'>텍스트를 찾을 수 없거나 OCR 오류가 발생했습니다.</span>")

    # ======================
    # 이미지 표시 (기존 함수)
    # ======================
    def show_frame(self, frame):
        if frame is None:
            return

        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb.shape
        bytes_per_line = ch * w

        qimg = QImage(
            rgb.data,
            w,
            h,
            bytes_per_line,
            QImage.Format_RGB888
        )

        pix = QPixmap.fromImage(qimg)

        self.label.setPixmap(
            pix.scaled(
                self.label.size(),
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation
            )
        )

    # ======================
    # 종료 시 동영상 중지
    # ======================
    def closeEvent(self, event):
        self.stop_video()
        event.accept()


# ======================
# 실행
# ======================
if __name__ == "__main__":
    app = QApplication(sys.argv)

    if platform.system() == 'Windows':
        font = QFont("Malgun Gothic", 10)
    elif platform.system() == 'Darwin':
        font = QFont("AppleGothic", 10)
    else:
        font = QFont("Sans Serif", 10)

    app.setFont(font)

    win = MainWindow()
    win.show()
    sys.exit(app.exec_())