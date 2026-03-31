"""
Format Loader Utility
Dynamically loads format modules from the formats/ directory
"""

import importlib.util
import sys
import json
from typing import Any, Dict
import logging
from logs_config import get_logger

logger = get_logger(__name__)


class FormatLoader:
    """Dynamically load format modules"""
    
    @staticmethod
    def load_format(format_path: str) -> Dict[str, Any]:
        """
        Load format module from file path
        """
        try:
            import os

            module_name = os.path.splitext(os.path.basename(format_path))[0]

            # Load strictly from local project format file.
            if os.path.exists(format_path):
                logger.info(f"Loading format module '{module_name}' from local file: {format_path}")
                spec = importlib.util.spec_from_file_location(module_name, format_path)
                if spec is None or spec.loader is None:
                    raise ImportError(f"Could not load spec from {format_path}")

                if module_name in sys.modules:
                    del sys.modules[module_name]
                module = importlib.util.module_from_spec(spec)
                sys.modules[module_name] = module
                spec.loader.exec_module(module)
            else:
                raise FileNotFoundError(f"Format '{module_name}' local file {format_path} does not exist.")
            
            logger.info(f"Successfully loaded format components for: {module_name}")
            
            # Standard component discovery
            claim_model = getattr(module, 'ClaimModel', None)
            response_model = getattr(module, 'ResponseModel', None)
            batch_model = getattr(module, 'BatchModel', None)

            # Explicitly load rules and totals from the module
            schema_description = getattr(module, 'SCHEMA_DESCRIPTION', '')
            calculate_totals_fn = getattr(module, 'calculate_totals', None)
            map_data_fn = getattr(module, 'map_extracted_data', None)
            section_builder_fn = getattr(module, 'section_builder', None)
            
            # Generate JSON schemas for the AI
            claim_schema = ""
            response_schema = ""
            if claim_model:
                try:
                    claim_schema = json.dumps(claim_model.model_json_schema(), indent=2)
                except Exception as e:
                    logger.warning(f"Could not generate Claim schema for {module_name}: {e}")
            
            if response_model:
                try:
                    response_schema = json.dumps(response_model.model_json_schema(), indent=2)
                except Exception as e:
                    logger.warning(f"Could not generate Response schema for {module_name}: {e}")

            batch_schema = ""
            if batch_model:
                try:
                    batch_schema = json.dumps(batch_model.model_json_schema(), indent=2)
                except Exception as e:
                    logger.warning(f"Could not generate Batch schema for {module_name}: {e}")

            return {
                'ClaimModel': claim_model,
                'ResponseModel': response_model,
                'BatchModel': batch_model,
                'SCHEMA_DESCRIPTION': schema_description,
                'json_schema': claim_schema,
                'response_json_schema': response_schema,
                'batch_json_schema': batch_schema,
                'calculate_totals': calculate_totals_fn,
                'map_extracted_data': map_data_fn,
                'section_builder': section_builder_fn,
                'module_name': module_name
            }
            
        except Exception as e:
            logger.error(f"Error loading format from {format_path}: {str(e)}")
            raise

    @staticmethod
    def get_schema_description(format_components: Dict[str, Any]) -> str:
        """Get schema description from format components"""
        return format_components.get('SCHEMA_DESCRIPTION', '')
    
    @staticmethod
    def create_response(
        format_components: Dict[str, Any],
        full_data: dict,
        document_type: str
    ) -> dict:
        """
        Create validated response using format components.
        """
        response_model = format_components.get('ResponseModel')
        module_name = format_components.get('module_name', document_type.lower())

        if response_model is None:
            logger.error(
                f"Validation skipped for {document_type}: ResponseModel missing in format module '{module_name}'. Returning unvalidated response."
            )
            return full_data
        if not callable(response_model):
            logger.error(
                f"Validation skipped for {document_type}: ResponseModel in module '{module_name}' is not callable ({type(response_model).__name__}). Returning unvalidated response."
            )
            return full_data
        
        try:
            # Validate with Pydantic model
            validated_response = response_model(**full_data)
            if hasattr(validated_response, "model_dump"):
                return validated_response.model_dump()
            logger.warning(
                f"Validated response for {document_type} from module '{module_name}' has no model_dump(). Returning raw validated object."
            )
            return validated_response
        except Exception as e:
            logger.error(f"Validation failed for {document_type}: {e}")
            return full_data
