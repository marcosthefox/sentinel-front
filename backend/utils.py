import numpy as np
import cv2

def calculate_ndvi(image):
    nir = image[:, :, 3].astype(float)
    red = image[:, :, 0].astype(float)
    ndvi = (nir - red) / (nir + red + 1e-10)
    ndvi = np.clip(ndvi, -1, 1)
    return ndvi

def percentage_of_ndvi(ndvi):
    total_pixels = ndvi.size
    sin_vegetacion = np.sum(ndvi < 0.2)
    vegetacion_moderada = np.sum((ndvi >= 0.2) & (ndvi < 0.5))
    vegetacion_densa = np.sum(ndvi >= 0.5)

    porcentaje_sin_vegetacion = (sin_vegetacion / total_pixels) * 100
    porcentaje_moderada = (vegetacion_moderada / total_pixels) * 100
    porcentaje_densa = (vegetacion_densa / total_pixels) * 100

    return {
        "no_vegetation": porcentaje_sin_vegetacion,
        "moderate_vegetation": porcentaje_moderada,
        "dense_vegetation": porcentaje_densa
    }

def calculate_evi(image):
    nir = image[:, :, 3].astype(float)
    red = image[:, :, 0].astype(float)
    blue = image[:, :, 2].astype(float)
    evi = 2.5 * (nir - red) / (nir + 6 * red - 7.5 * blue + 1)
    evi[np.isnan(evi)] = 0
    evi = np.clip(evi, -1, 1)
    return evi

def percentage_of_evi(evi):
    total_pixels = evi.size
    vegetacion_baja = np.sum(evi < 0.2)
    vegetacion_moderada = np.sum((evi >= 0.2) & (evi < 0.5))
    vegetacion_densa = np.sum(evi >= 0.5)

    porcentaje_baja = (vegetacion_baja / total_pixels) * 100
    porcentaje_moderada = (vegetacion_moderada / total_pixels) * 100
    porcentaje_densa = (vegetacion_densa / total_pixels) * 100

    return {
        "no_vegetation": porcentaje_baja,
        "moderate_vegetation": porcentaje_moderada,
        "dense_vegetation": porcentaje_densa
    }


def apply_morphological_filters(index_array):
    index_image = ((index_array - np.nanmin(index_array)) / (np.nanmax(index_array) - np.nanmin(index_array)) * 255).astype(np.uint8)
    kernel = np.ones((5, 5), np.uint8)
    erosion = cv2.erode(index_image, kernel, iterations=1)
    dilation = cv2.dilate(erosion, kernel, iterations=1)
    opening = cv2.morphologyEx(dilation, cv2.MORPH_OPEN, kernel)
    closing = cv2.morphologyEx(opening, cv2.MORPH_CLOSE, kernel)
    return closing

def percentage_of_colors(image_array):
    total_pixels = image_array.size
    black_pixels = np.sum(image_array == 0)
    white_pixels = np.sum(image_array == 255)
    gray_pixels = total_pixels - (black_pixels + white_pixels)

    black_percentage = (black_pixels / total_pixels) * 100
    gray_percentage = (gray_pixels / total_pixels) * 100
    white_percentage = (white_pixels / total_pixels) * 100

    return {
        "white": white_percentage,
        "gray": gray_percentage,
        "black": black_percentage
    }