# ADR 0012: Optical (SSIM) analysis runs inside the control-plane Lambda

## Status
Accepted

## Context
The optical step compares two photos (red vs blue light) with SSIM and turns the deviation into a
band and a 0-5 score. The original `analysis.py` used OpenCV + scikit-image. Measured for Lambda
(Linux x86_64, Python 3.13): numpy + opencv-python-headless + scikit-image = 441 MB unzipped / 147 MB
zipped, over Lambda's 250 MB (unzipped) and 50 MB (direct zip upload) limits. OpenCV alone is 153 MB,
and the control plane still reaches 267 MB with only numpy + OpenCV.

## Decision
Keep a single Lambda. Re-implement the same algorithm with numpy + Pillow (`app/optical.py`):
- SSIM: skimage defaults (7x7 uniform window, K1 0.01, K2 0.03, sample covariance, data_range 255,
  3 px border cropped). Verified against scikit-image: max difference ~5e-16.
- Grayscale uses OpenCV's fixed-point BGR2GRAY formula; histogram equalisation reproduces
  `cv2.equalizeHist`; EXIF orientation is applied (OpenCV's imdecode does this, Pillow does not).
- Control-plane zip: 109 MB unzipped / 32 MB zipped. boto3 is not bundled (runtime provides it).

Images go browser -> S3 through presigned POST (10 MB cap, image/* only), not through API Gateway
(10 MB limit) or Lambda (6 MB payload). S3 keys are generated server-side and stored on the
diagnosis; the analysis step never trusts a client-supplied key.

deviation = 1 - ssim_score. Bands (owner-confirmed): < 0.16 Variable Diagnosis; <= 0.20 Borderline;
otherwise Suggestive of Dysplasia. Score = lookup(provisional diagnosis, band) in `scoring_engine.py`
(generated from Scoring_excel_0_to_5_1.xlsx; Fibroma + Suggestive of Dysplasia = 3; Variable
Diagnosis = 0 in all bands, dentist-confirmed).

## Consequences
- Same-size image pairs give results identical to the original pipeline. If the two images differ in
  size, the resize step differs from OpenCV's bilinear by up to ~0.004 SSIM (band width is 0.04).
  The API returns `resized: true` when this happens.
- No ECR, Docker or second Lambda. A container image (ADR to come) is still the likely home for DL
  inference, which is skipped in this prototype.
- `provisional_diagnosis` is request input to the optical step while the DL step is skipped.
- Bucket objects expire after 30 days (placeholder retention - confirm with the clinic).
- Lambda: 1024 MB, 30 s timeout (12 MP pair ~4 s locally).