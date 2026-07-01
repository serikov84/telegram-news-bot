import logging

import replicate

import config

log = logging.getLogger(__name__)


def generate_image(title):
    """Генерирует изображение через Replicate API"""
    try:
        replicate.api_token = config.REPLICATE_API_KEY
        prompt = f"Professional news illustration about: {title}. High quality, clean design."
        output = replicate.run("stability-ai/stable-diffusion-3", input={"prompt": prompt})
        if output:
            return output[0]
    except Exception as e:
        log.error(f"Image generation error: {e}")
    return None
