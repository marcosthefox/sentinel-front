# Importar bibliotecas necesarias
from flask import Flask, request, jsonify, send_file
from flasgger import Swagger, swag_from
import numpy as np
import requests
from sentinelhub import SHConfig, SentinelHubRequest, DataCollection, MimeType, BBox, bbox_to_dimensions, CRS
from PIL import Image
import io
import os
import base64
from evalscript import evalscript_ir, evalscript_true_color
from utils import calculate_ndvi, calculate_evi, apply_morphological_filters, percentage_of_colors, percentage_of_evi, percentage_of_ndvi
from flask_cors import CORS

app = Flask(__name__)
swagger = Swagger(app)
CORS(app)
auth_url = 'https://services.sentinel-hub.com/auth/realms/main/protocol/openid-connect/token'

default_client_id = os.getenv('SENTINEL_CLIENT_ID', '9c0c3d7a-eb52-4ce1-bc03-b06f43f1b3eb')
default_client_secret = os.getenv('SENTINEL_CLIENT_SECRET', 'juqsKd57rYsrLGCevRjhrlG7QwKm1WVw')
default_port = os.getenv('SERVER_PORT', 8500)

@app.route('/api/sentinel/download_image', methods=['POST'])
@swag_from({
    'parameters': [
        {
            'name': 'evi',
            'in': 'query',
            'type': 'boolean',
            'required': False,
            'description': 'Calcular y retornar la imagen EVI'
        },
        {
            'name': 'ndvi',
            'in': 'query',
            'type': 'boolean',
            'required': False,
            'description': 'Calcular y retornar la imagen NDVI'
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
            'content': {
                'image/png': {}
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
def download_image():
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
        top_left_point = data['top_left_point']
        field_size = data['field_size']
        access_token = token

        config = SHConfig()
        config.sh_client_id = default_client_id
        config.sh_client_secret = default_client_secret
        config.sh_base_url = 'https://sh.dataspace.copernicus.eu'
        config.sh_oauth_token = access_token

        top_left_x, top_left_y = top_left_point
        bottom_right_x = top_left_x + (field_size / 111320) / np.cos(np.radians(top_left_y))
        bottom_right_y = top_left_y - (field_size / 111320)

        aoi_coords_wgs84 = [top_left_x, top_left_y, bottom_right_x, bottom_right_y]
        print("Coordenadas: ", aoi_coords_wgs84)
        
        image_width = 962
        image_height = 1175
        
        aoi_bbox = BBox(bbox=aoi_coords_wgs84, crs=CRS.WGS84)
        aoi_size = (image_width, image_height)

        if evi_param or ndvi_param:
            evalscript = evalscript_ir
        else:
            evalscript = evalscript_true_color
        
        response_sentinel = SentinelHubRequest(
            evalscript=evalscript,
            input_data=[
                SentinelHubRequest.input_data(
                    data_collection=DataCollection.SENTINEL2_L2A,
                    time_interval=(start_date, end_date),
                    other_args={"dataFilter": {"mosaickingOrder": "leastCC"}},
                )
            ],
            responses=[SentinelHubRequest.output_response("default", MimeType.PNG)],
            bbox=aoi_bbox,
            size=aoi_size,
            config=config,
        )

        images = response_sentinel.get_data()
        image_data = images[0]

        image_array = np.array(image_data)

        if evi_param and not ndvi_param:
            evi = calculate_evi(image_array)
            evi_filtered = apply_morphological_filters(evi)

            # Normalizar y convertir a imagen
            evi_image = ((evi_filtered - np.nanmin(evi_filtered)) / (np.nanmax(evi_filtered) - np.nanmin(evi_filtered)) * 255).astype(np.uint8)
            
            evi_pil_image = Image.fromarray(evi_image)
            buffer = io.BytesIO()
            evi_pil_image.save(buffer, format="PNG")
            buffer.seek(0)

            return send_file(buffer, mimetype='image/png', as_attachment=True, download_name='evi.png')
        
        elif ndvi_param and not evi_param:
            ndvi = calculate_ndvi(image_array)
            ndvi_filtered = apply_morphological_filters(ndvi)
    
            # Normalizar y convertir a imagen
            ndvi_image = ((ndvi_filtered - np.nanmin(ndvi_filtered)) / (np.nanmax(ndvi_filtered) - np.nanmin(ndvi_filtered)) * 255).astype(np.uint8)

            ndvi_pil_image = Image.fromarray(ndvi_image)
            buffer = io.BytesIO()
            ndvi_pil_image.save(buffer, format="PNG")
            buffer.seek(0)
            return send_file(buffer, mimetype='image/png', as_attachment=True, download_name='ndvi.png')
        
        else:
            # Escalar los valores a [0, 1]
            image_array = np.clip(image_array / 255.0, 0, 1)

            # Aplicar corrección gamma
            gamma = 1.5
            image_array = np.power(image_array, 1.0 / gamma)

            # Escalar los valores de nuevo a [0, 255]
            image_array = (image_array * 255).astype(np.uint8)

            image = Image.fromarray(image_array)

            # estiramiento de histograma
            def histogram_stretch(image):
                array = np.asarray(image).astype(np.float32)
                p2, p98 = np.percentile(array, (2, 98))
                array = np.clip((array - p2) / (p98 - p2) * 255.0, 0, 255)
                return Image.fromarray(array.astype(np.uint8))

            image_stretched = histogram_stretch(image)

            buffer = io.BytesIO()
            image_stretched.save(buffer, format="PNG")
            buffer.seek(0)

            return send_file(buffer, mimetype='image/png', as_attachment=True, download_name='image.png')

    except Exception as e:
        return jsonify({"error": str(e)}), 500
    

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
        top_left_point = data['top_left_point']
        field_size = data['field_size']
        access_token = token

        config = SHConfig()
        config.sh_client_id = default_client_id
        config.sh_client_secret = default_client_secret
        config.sh_base_url = 'https://sh.dataspace.copernicus.eu'
        config.sh_oauth_token = access_token

        top_left_x, top_left_y = top_left_point
        bottom_right_x = top_left_x + (field_size / 111320) / np.cos(np.radians(top_left_y))
        bottom_right_y = top_left_y - (field_size / 111320)

        aoi_coords_wgs84 = [top_left_x, top_left_y, bottom_right_x, bottom_right_y]
        print("Coordenadas: ", aoi_coords_wgs84)
        
        image_width = 962
        image_height = 1175
        
        aoi_bbox = BBox(bbox=aoi_coords_wgs84, crs=CRS.WGS84)
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
            bbox=aoi_bbox,
            size=aoi_size,
            config=config,
        )
        images_color = response_sentinel_color.get_data()
        image_data_color = images_color[0]
        image_array_color = np.array(image_data_color)

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
            bbox=aoi_bbox,
            size=aoi_size,
            config=config,
        )
        images_ir = response_sentinel_ir.get_data()
        image_data_ir = images_ir[0]
        image_array_ir = np.array(image_data_ir)

        if evi_param and not ndvi_param:
            """
            =============== INTERPRETACION EVI =================
            - Valores negativos y 0: agua o areas sin vegetacion
            - Valores entre 0 y 0.2: sin vegetacion
            - Valores entre 0.2 y 0.5: vegetacion moderada (praderas, pastizal)
            - Valores mayores a 0.5: vegetacion densa (bosques, selvas)
            """
            evi = calculate_evi(image_array_ir)
            
            print(f"EVI - Max: {np.max(evi)}, Min: {np.min(evi)}, Mean: {np.mean(evi)}")
            # print(f"EVI - Algunos valores: {evi.flatten()[:100]}")  # Imprimir los primeros 100 valores
            # print(f"Total de valores EVI: {evi.size}")

            porcentajes_vegetacion = percentage_of_evi(evi)

            image_array_color = np.clip(image_array_color / 255.0, 0, 1)
            gamma = 1.5
            image_array_color = np.power(image_array_color, 1.0 / gamma)
            image_array_color = (image_array_color * 255).astype(np.uint8)
            image = Image.fromarray(image_array_color)

            # estiramiento de histograma
            def histogram_stretch(image):
                array = np.asarray(image).astype(np.float32)
                p2, p98 = np.percentile(array, (2, 98))
                array = np.clip((array - p2) / (p98 - p2) * 255.0, 0, 255)
                return Image.fromarray(array.astype(np.uint8))

            image_stretched = histogram_stretch(image)
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

            # estiramiento de histograma
            def histogram_stretch(image):
                array = np.asarray(image).astype(np.float32)
                p2, p98 = np.percentile(array, (2, 98))
                array = np.clip((array - p2) / (p98 - p2) * 255.0, 0, 255)
                return Image.fromarray(array.astype(np.uint8))

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

            # estiramiento de histograma
            def histogram_stretch(image):
                array = np.asarray(image).astype(np.float32)
                p2, p98 = np.percentile(array, (2, 98))
                array = np.clip((array - p2) / (p98 - p2) * 255.0, 0, 255)
                return Image.fromarray(array.astype(np.uint8))

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