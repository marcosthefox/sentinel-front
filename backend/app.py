# Importar bibliotecas necesarias
from flask import Flask, request, jsonify, send_file
from flasgger import Swagger, swag_from
import numpy as np
import requests
from sentinelhub import SHConfig, SentinelHubRequest, DataCollection, MimeType, BBox, bbox_to_dimensions, CRS, Geometry
from PIL import Image, ImageDraw, ImageEnhance
import io
import os
import base64
from evalscript import evalscript_ir, evalscript_true_color
from utils import calculate_ndvi, calculate_evi, apply_morphological_filters, percentage_of_evi, percentage_of_ndvi
from shapely.geometry import Polygon, mapping
import rasterio.features
from flask_cors import CORS

app = Flask(__name__)
swagger = Swagger(app)
CORS(app)
auth_url = 'https://services.sentinel-hub.com/auth/realms/main/protocol/openid-connect/token'

default_client_id = os.getenv('SENTINEL_CLIENT_ID', 'f5092bdc-c661-4e4d-b589-a1c099975720')
default_client_secret = os.getenv('SENTINEL_CLIENT_SECRET', 'HVjucPMH7tThMDFZf18y9I1WMON3S39K')
default_port = os.getenv('SERVER_PORT', 8500)

def histogram_stretch(image):
                array = np.asarray(image).astype(np.float32)
                p2, p98 = np.percentile(array, (2, 98))
                array = np.clip((array - p2) / (p98 - p2) * 255.0, 0, 255)
                return Image.fromarray(array.astype(np.uint8))

@app.route('/api/sentinel/percentage', methods=['POST'])
@swag_from({
    'parameters': [
        {
            'name': 'evi',
            'in': 'query',
            'type': 'boolean',
            'required': False,
            'description': 'Retorna la imagen EVI codificada en base64, los porcentajes de color y los porcentajes de vegetación'
        },
        {
            'name': 'ndvi',
            'in': 'query',
            'type': 'boolean',
            'required': False,
            'description': 'Retorna la imagen NDVI codificada en base64, los porcentajes de color y los porcentajes de vegetación'
        },
        {
            'in': 'body',
            'name': 'body',
            'required': True,
            'schema': {
                'type': 'object',
                'properties': {
                    'start_date': {
                        'type': 'string',
                        'example': '2020-12-01'
                    },
                    'end_date': {
                        'type': 'string',
                        'example': '2020-12-31'
                    },
                    'top_left_point': {
                        'type': 'array',
                        'items': {
                            'type': 'number'
                        },
                        'example': [15.461282, 46.757161]
                    },
                    'field_size': {
                        'type': 'number',
                        'example': 1000
                    }
                }
            }
        }
    ],
    'responses': {
        200: {
            'description': 'Imagen descargada exitosamente',
            'schema': {
                'type': 'object',
                'properties': {
                    'image': {
                        'type': 'Imagen codificada en base64'
                    },
                    'percentage_of_colors': {
                        'type': 'objeto con los campos \'black\', \'gray\' y \'white\''
                    },
                    'percentage_of_evi': {
                        'type': 'objeto con los campos \'no_vegetation\', \'moderate_vegetation\' y \'dense_vegetation\''
                    }
                }
            }
        },
        400: {
            'description': 'Error al descargar la imagen'
        },
        500: {
            'description': 'Error del servidor'
        }
    }
})
def download_image_with_percentages():
    try:
        evi_param = request.args.get('evi')
        if evi_param == 'true':
            evi_param = True
        else:
            evi_param = False
        ndvi_param = request.args.get('ndvi')
        if ndvi_param == 'true':
            ndvi_param = True
        else:
            ndvi_param = False

        data = {
            'grant_type': 'client_credentials',
            'client_id': default_client_id,
            'client_secret': default_client_secret
        }

        headers = {
            'content-type': 'application/x-www-form-urlencoded'
        }

        response = requests.post(auth_url, headers=headers, data=data)
        token = None

        if response.status_code == 200:
            token = response.json().get('access_token')
        else:
            return jsonify({"error": response.status_code, "message": response.text}), response.status_code
    
        data = request.get_json()
        start_date = data['start_date']
        end_date = data['end_date']
        polygon = data['polygon']
        access_token = token

        config = SHConfig()
        config.sh_client_id = default_client_id
        config.sh_client_secret = default_client_secret
        config.sh_base_url = 'https://sh.dataspace.copernicus.eu'
        config.sh_oauth_token = access_token

        # Convertir el polígono en una geometría válida
        aoi_geometry = Geometry(geometry={'type': 'Polygon', 'coordinates': [polygon]}, crs=CRS.WGS84)
        print("Polígono: ", aoi_geometry)
        
        image_width = 962
        image_height = 1175
        aoi_size = (image_width, image_height)
        
        # *************** imagen en color **************
        response_sentinel_color = SentinelHubRequest(
            evalscript=evalscript_true_color,
            input_data=[
                SentinelHubRequest.input_data(
                    data_collection=DataCollection.SENTINEL2_L2A,
                    time_interval=(start_date, end_date),
                    other_args={"dataFilter": {"mosaickingOrder": "leastCC"}},
                )
            ],
            responses=[SentinelHubRequest.output_response("default", MimeType.PNG)],
            geometry=aoi_geometry,
            # size=aoi_size,
            config=config,
        )
        images_color = response_sentinel_color.get_data()
        image_data_color = images_color[0]
        image_array_color = np.array(image_data_color)

        polygon = Polygon(polygon)
        transform_color = rasterio.transform.from_bounds(*aoi_geometry.bbox, image_array_color.shape[1], image_array_color.shape[0])
        mask_color = rasterio.features.geometry_mask([mapping(polygon)], transform=transform_color, invert=True, out_shape=(image_array_color.shape[0], image_array_color.shape[1]))

        # Print the counts of pixels inside and outside the polygon
        pixels_inside_polygon = np.sum(mask_color)
        pixels_outside_polygon = mask_color.size - pixels_inside_polygon
        print(f"Pixels inside polygon: {pixels_inside_polygon}")
        print(f"Pixels outside polygon: {pixels_outside_polygon}")

        # Apply mask to the image array
        for i in range(image_array_color.shape[2]):  # Apply the mask to each channel
            image_array_color[:,:,i] = image_array_color[:,:,i] * mask_color

        # *************** imagen infrarroja **************
        response_sentinel_ir = SentinelHubRequest(
            evalscript=evalscript_ir,
            input_data=[
                SentinelHubRequest.input_data(
                    data_collection=DataCollection.SENTINEL2_L2A,
                    time_interval=(start_date, end_date),
                    other_args={"dataFilter": {"mosaickingOrder": "leastCC"}},
                )
            ],
            responses=[SentinelHubRequest.output_response("default", MimeType.PNG)],
            geometry=aoi_geometry,
            # size=aoi_size,
            config=config,
        )
        images_ir = response_sentinel_ir.get_data()
        image_data_ir = images_ir[0]
        image_array_ir = np.array(image_data_ir)

        polygon = Polygon(polygon)

        transform_ir = rasterio.transform.from_bounds(*aoi_geometry.bbox, image_array_ir.shape[1], image_array_ir.shape[0])
        mask_ir = rasterio.features.geometry_mask([mapping(polygon)], transform=transform_ir, invert=True, out_shape=(image_array_ir.shape[0], image_array_ir.shape[1]))

        # Print the counts of pixels inside and outside the polygon
        pixels_inside_polygon = np.sum(mask_ir)
        pixels_outside_polygon = mask_ir.size - pixels_inside_polygon
        print(f"Pixels inside polygon: {pixels_inside_polygon}")
        print(f"Pixels outside polygon: {pixels_outside_polygon}")

        # Apply mask to the image array
        for i in range(image_array_ir.shape[2]):  # Apply the mask to each channel
            image_array_ir[:,:,i] = image_array_ir[:,:,i] * mask_ir

        if evi_param and not ndvi_param:
            """
            =============== INTERPRETACION EVI =================
            - Valores negativos y 0: agua o areas sin vegetacion
            - Valores entre 0 y 0.2: sin vegetacion
            - Valores entre 0.2 y 0.5: vegetacion moderada (praderas, pastizal)
            - Valores mayores a 0.5: vegetacion densa (bosques, selvas)
            """
            evi = calculate_evi(image_array_ir, mask_ir)

            # Guardar valores de EVI en un archivo de texto
            np.savetxt('./evi_values.txt', evi, fmt='%0.8f')
            
            print(f"EVI - Max: {np.max(evi)}, Min: {np.min(evi)}, Mean: {np.mean(evi)}")
            # print(f"EVI - Algunos valores:")  # Imprimir los primeros 100 valores
            # print(evi.flatten()[:100])
            print(f"Total de valores EVI: {evi.size}")

            porcentajes_vegetacion = percentage_of_evi(evi)

            image_array_color = np.clip(image_array_color / 255.0, 0, 1)
            gamma = 1.5
            image_array_color = np.power(image_array_color, 1.0 / gamma)
            image_array_color = (image_array_color * 255).astype(np.uint8)
            image = Image.fromarray(image_array_color)

            image_stretched = histogram_stretch(image)

            enhancer = ImageEnhance.Brightness(image_stretched)
            image_stretched = enhancer.enhance(1.1)  # Increase brightness by 50%
            mask_image = Image.new('L', (image.width, image.height), 0)

            transform = rasterio.transform.from_bounds(*aoi_geometry.bbox, image.width, image.height)
            mask = rasterio.features.geometry_mask([mapping(polygon)], transform=transform, invert=True, out_shape=(image.height, image.width))

            mask_image.paste(255, mask=Image.fromarray(mask.astype(np.uint8) * 255))

            # Convert to RGBA and apply mask
            image_stretched = image_stretched.convert("RGBA")
            mask = mask_image.convert("L")
            image_stretched.putalpha(mask)

            buffer = io.BytesIO()
            image_stretched.save(buffer, format="PNG")
            buffer.seek(0)

            img_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')

            return jsonify({"image": img_base64, "percentage_of_evi": porcentajes_vegetacion})
                
        elif ndvi_param and not evi_param:
            """
            =============== INTERPRETACION NDVI =================
            - Valores entre -1.0 y 0.0: Agua o áreas sin vegetación.
            - Valores entre 0.0 y 0.2: Suelo desnudo, áreas urbanizadas o sin vegetación.
            - Valores entre 0.2 y 0.5: Vegetación moderada (praderas, pastizales).
            - Valores mayores a 0.5: Vegetación densa (bosques, selvas).
            """
            ndvi = calculate_ndvi(image_array_ir)

            print(f"NDVI - Max: {np.max(ndvi)}, Min: {np.min(ndvi)}, Mean: {np.mean(ndvi)}")
            # print(f"NDVI - Algunos valores: {ndvi.flatten()[:10]}")

            porcentajes_vegetacion = percentage_of_ndvi(ndvi)

            image_array_color = np.clip(image_array_color / 255.0, 0, 1)
            gamma = 1.5
            image_array_color = np.power(image_array_color, 1.0 / gamma)
            image_array_color = (image_array_color * 255).astype(np.uint8)
            image = Image.fromarray(image_array_color)

            image_stretched = histogram_stretch(image)
            buffer = io.BytesIO()
            image_stretched.save(buffer, format="PNG")
            buffer.seek(0)
            
            img_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')

            return jsonify({"image": img_base64, "percentage_of_ndvi": porcentajes_vegetacion})
        
        else:
            # Escalar los valores a [0, 1]
            image_array_color = np.clip(image_array_color / 255.0, 0, 1)

            # Aplicar corrección gamma
            gamma = 1.5
            image_array_color = np.power(image_array_color, 1.0 / gamma)

            # Escalar los valores de nuevo a [0, 255]
            image_array_color = (image_array_color * 255).astype(np.uint8)

            image = Image.fromarray(image_array_color)

            image_stretched = histogram_stretch(image)

            buffer = io.BytesIO()
            image_stretched.save(buffer, format="PNG")
            buffer.seek(0)

            img_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
            return jsonify({"image": img_base64})

    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=default_port)