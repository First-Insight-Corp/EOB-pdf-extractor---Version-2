"""
Format Loader Utility
Dynamically loads format modules from the formats/ directory
"""

import importlib.util
import sys
import json
from typing import Any, Dict
import logging

logger = logging.getLogger(__name__)


class FormatLoader:
    """Dynamically load format modules"""
    
    @staticmethod
    def load_format(format_path: str) -> Dict[str, Any]:
        """
        Load format module from file path
        """
        try:
            import os
            import types
            from db import db, DocumentFormat
            
            module_name = os.path.splitext(os.path.basename(format_path))[0]
            module = None
            
            # 1. Try to load from database first (Source of Truth)
            if db:
                try:
                    session = db.get_session()
                    fmt = session.query(DocumentFormat).filter_by(short_name=module_name).first()
                    session.close()
                    
                    if fmt and fmt.python_code:
                        logger.info(f"Loading format module '{module_name}' from database.")
                        module = types.ModuleType(module_name)
                        # Ensure we don't accidentally reuse an old module from sys.modules
                        if module_name in sys.modules:
                            del sys.modules[module_name]
                        sys.modules[module_name] = module
                        exec(fmt.python_code, module.__dict__)
                except Exception as db_e:
                    logger.warning(f"Failed to load format '{module_name}' from database: {db_e}. Falling back to disk if possible.")
            
            # 2. Fall back to local file if not in DB or DB load failed
            if module is None:
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
                    raise FileNotFoundError(f"Format '{module_name}' not found in database and local file {format_path} does not exist.")
            
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
        response_model = format_components['ResponseModel']
        
        try:
            # Validate with Pydantic model
            validated_response = response_model(**full_data)
            return validated_response.model_dump()
        except Exception as e:
            logger.error(f"Validation failed for {document_type}: {e}")
            return full_data
