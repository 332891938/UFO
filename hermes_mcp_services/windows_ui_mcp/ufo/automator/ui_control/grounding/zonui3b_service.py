# ZonUI-3B本地推理服务
# 基于 Qwen2.5-VL-3B + ZonUI-3B 微调权重，实现截图+文本→坐标定位

import ast
import logging
from typing import Optional, Tuple

import torch
from PIL import Image
from transformers import (
    Qwen2_5_VLForConditionalGeneration,
    AutoTokenizer,
    AutoProcessor,
)
from transformers.generation import GenerationConfig
from transformers.models.qwen2_vl.image_processing_qwen2_vl_fast import smart_resize

logger = logging.getLogger(__name__)


class ZonUI3BService:
    """ZonUI-3B本地推理服务。

    单个RTX 4090 (24GB)即可运行，bfloat16约需~8GB显存。
    """

    _instance: Optional["ZonUI3BService"] = None

    @classmethod
    def get_instance(cls, model_path: Optional[str] = None) -> "ZonUI3BService":
        """获取单例（避免重复加载模型）。"""
        if cls._instance is None:
            if model_path is None:
                raise ValueError("首次调用必须提供model_path")
            cls._instance = cls(model_path)
        return cls._instance

    def __init__(self, model_path: str):
        logger.info(f"Loading ZonUI-3B from {model_path}...")

        self.model = Qwen2_5_VLForConditionalGeneration.from_pretrained(
            model_path,
            device_map="auto",
            torch_dtype=torch.bfloat16,
            attn_implementation="sdpa",
        ).eval()

        self.processor = AutoProcessor.from_pretrained(model_path)
        self.tokenizer = AutoTokenizer.from_pretrained(
            model_path, trust_remote_code=True
        )

        generation_config = GenerationConfig.from_pretrained(
            model_path, trust_remote_code=True
        )
        generation_config.max_length = 4096
        generation_config.do_sample = False
        generation_config.temperature = 0.0
        self.model.generation_config = generation_config

        self.min_pixels = 256 * 28 * 28
        self.max_pixels = 1280 * 28 * 28
        logger.info("ZonUI-3B loaded successfully.")

    def predict(
        self,
        image_path: str,
        query: str,
    ) -> Tuple[float, float, float, float]:
        """给定截图路径和文字描述，返回归一化坐标和原始坐标。

        Args:
            image_path: 截图文件路径
            query: 要查找的UI元素描述，如 "Save button" 或 "关闭按钮"

        Returns:
            (normalized_x, normalized_y, absolute_x, absolute_y)
            - normalized_x/y: [0.0, 1.0] 归一化坐标，相对于原图
            - absolute_x/y: 原图像素坐标
        """
        image = Image.open(image_path).convert("RGB")
        orig_width, orig_height = image.width, image.height

        # 按模型要求缩放
        resized_height, resized_width = smart_resize(
            orig_height,
            orig_width,
            factor=self.processor.image_processor.patch_size
            * self.processor.image_processor.merge_size,
            min_pixels=self.min_pixels,
            max_pixels=self.max_pixels,
        )
        resized_image = image.resize((resized_width, resized_height))

        _SYSTEM = (
            "Based on the screenshot of the page, I give a text description "
            "and you give its corresponding location. The coordinate represents "
            "a clickable location [x, y] for an element."
        )

        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": _SYSTEM},
                    {
                        "type": "image",
                        "image": image_path,
                        "min_pixels": self.min_pixels,
                        "max_pixels": self.max_pixels,
                    },
                    {"type": "text", "text": query},
                ],
            }
        ]

        text = self.processor.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True
        )

        inputs = self.processor(
            text=[text],
            images=[resized_image],
            return_tensors="pt",
        ).to(self.model.device)

        with torch.no_grad():
            generated_ids = self.model.generate(**inputs)

        generated_ids_trimmed = [
            out_ids[len(in_ids):]
            for in_ids, out_ids in zip(inputs.input_ids, generated_ids)
        ]
        output_text = self.processor.batch_decode(
            generated_ids_trimmed,
            skip_special_tokens=True,
            clean_up_tokenization_spaces=False,
        )[0].strip()

        # 解析坐标
        try:
            coordinates = ast.literal_eval(output_text)
            if len(coordinates) == 2:
                norm_x = coordinates[0] / resized_width
                norm_y = coordinates[1] / resized_height
                abs_x = norm_x * orig_width
                abs_y = norm_y * orig_height
                return (norm_x, norm_y, abs_x, abs_y)
        except Exception:
            logger.warning(f"Failed to parse ZonUI-3B output: {output_text}")
            raise ValueError(f"Invalid ZonUI-3B output: {output_text}")

        raise ValueError(f"Unexpected output format: {output_text}")
