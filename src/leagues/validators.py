from typing import List, Dict, Optional
from dataclasses import dataclass

@dataclass
class ValidationResult:
    is_valid: bool
    errors: List[str]
    warnings: List[str]

class RulesetValidator:
    """Validates ruleset configurations."""
    
    @staticmethod
    def validate_scoring_config(config: Dict) -> ValidationResult:
        """Validate scoring configuration section."""
        errors = []
        warnings = []
        
        # Check required sections
        if 'scoring' not in config:
            errors.append("Missing 'scoring' section in configuration")
            return ValidationResult(False, errors, warnings)
            
        scoring = config['scoring']
        
        # Validate each discipline
        for discipline in ['lead', 'boulder', 'speed']:
            if discipline not in scoring:
                errors.append(f"Missing '{discipline}' configuration in scoring section")
                continue
                
            discipline_config = scoring[discipline]
            
            # Validate base points
            if 'base_points' not in discipline_config:
                errors.append(f"Missing 'base_points' in {discipline} configuration")
            
            # Validate ranking points
            if 'ranking_points' not in discipline_config:
                errors.append(f"Missing 'ranking_points' in {discipline} configuration")
            else:
                ranking_points = discipline_config['ranking_points']
                if not any(key in ranking_points for key in ['provincial', 'world_cup']):
                    errors.append(f"Missing primary competition level in {discipline} ranking points")
                
                # Check multipliers
                for level, config in ranking_points.items():
                    if isinstance(config, dict) and 'multiplier' in config:
                        if not (0 < config['multiplier'] <= 2):
                            warnings.append(f"Unusual multiplier value ({config['multiplier']}) for {level} in {discipline}")
        
        return ValidationResult(len(errors) == 0, errors, warnings)
    
    @staticmethod
    def validate_ranking_config(config: Dict) -> ValidationResult:
        """Validate ranking configuration section."""
        errors = []
        warnings = []
        
        # Check required sections
        if 'ranking' not in config:
            errors.append("Missing 'ranking' section in configuration")
            return ValidationResult(False, errors, warnings)
            
        ranking = config['ranking']
        
        # Validate best_n_results
        if 'best_n_results' not in ranking:
            errors.append("Missing 'best_n_results' in ranking configuration")
        elif not isinstance(ranking['best_n_results'], int) or ranking['best_n_results'] <= 0:
            errors.append("Invalid 'best_n_results' value - must be a positive integer")
            
        # Validate tiebreak
        if 'tiebreak' not in ranking:
            errors.append("Missing 'tiebreak' configuration in ranking section")
        else:
            tiebreak = ranking['tiebreak']
            if 'methods' not in tiebreak:
                errors.append("Missing 'methods' in tiebreak configuration")
            elif not isinstance(tiebreak['methods'], list):
                errors.append("Tiebreak 'methods' must be a list")
            else:
                valid_methods = {'head_to_head', 'most_recent', 'countback', 'most_provincial'}
                invalid_methods = set(tiebreak['methods']) - valid_methods
                if invalid_methods:
                    errors.append(f"Invalid tiebreak methods: {', '.join(invalid_methods)}")
        
        return ValidationResult(len(errors) == 0, errors, warnings)
    
    @staticmethod
    def validate_qualification_criteria(config: Dict) -> ValidationResult:
        """Validate qualification criteria configuration."""
        errors = []
        warnings = []
        
        # Check required sections
        if 'qualification_criteria' not in config:
            errors.append("Missing 'qualification_criteria' section in configuration")
            return ValidationResult(False, errors, warnings)
            
        criteria = config['qualification_criteria']
        
        # Validate basic criteria
        required_fields = ['min_competitions', 'min_points']
        for field in required_fields:
            if field not in criteria:
                errors.append(f"Missing '{field}' in qualification criteria")
            elif not isinstance(criteria[field], (int, float)) or criteria[field] <= 0:
                errors.append(f"Invalid '{field}' value - must be a positive number")
                
        # Validate category-specific requirements
        if 'category_requirements' in criteria:
            for category, reqs in criteria['category_requirements'].items():
                for field in required_fields:
                    if field not in reqs:
                        warnings.append(f"Missing '{field}' in {category} category requirements")
                    elif not isinstance(reqs[field], (int, float)) or reqs[field] <= 0:
                        errors.append(f"Invalid '{field}' value for {category} category")
        
        return ValidationResult(len(errors) == 0, errors, warnings)
    
    @staticmethod
    def validate_derogation_config(config: Dict) -> ValidationResult:
        """Validate derogation configuration."""
        errors = []
        warnings = []
        
        # Check if derogation is present
        if 'derogation' not in config:
            warnings.append("Missing 'derogation' section - derogation features will be disabled")
            return ValidationResult(True, errors, warnings)
            
        derogation = config['derogation']
        
        # Validate enabled flag
        if 'enabled' not in derogation:
            errors.append("Missing 'enabled' flag in derogation configuration")
            
        # Validate rules if derogation is enabled
        if derogation.get('enabled', False):
            if 'rules' not in derogation:
                errors.append("Missing 'rules' in derogation configuration")
            else:
                rules = derogation['rules']
                required_rule_fields = [
                    'allow_participation',
                    'points_handling',
                    'ranking_display'
                ]
                for field in required_rule_fields:
                    if field not in rules:
                        errors.append(f"Missing '{field}' in derogation rules")
                        
                # Validate points handling method
                valid_handling_methods = {'redistribute', 'keep', 'zero'}
                if rules.get('points_handling') not in valid_handling_methods:
                    errors.append(f"Invalid points handling method. Must be one of: {', '.join(valid_handling_methods)}")
        
        return ValidationResult(len(errors) == 0, errors, warnings)
    
    @classmethod
    def validate_ruleset(cls, config: Dict) -> ValidationResult:
        """Validate complete ruleset configuration."""
        all_errors = []
        all_warnings = []
        
        # Validate each section
        sections = [
            ('scoring', cls.validate_scoring_config),
            ('ranking', cls.validate_ranking_config),
            ('qualification', cls.validate_qualification_criteria),
            ('derogation', cls.validate_derogation_config)
        ]
        
        for section_name, validator in sections:
            result = validator(config)
            if not result.is_valid:
                all_errors.extend([f"{section_name}: {error}" for error in result.errors])
            all_warnings.extend([f"{section_name}: {warning}" for warning in result.warnings])
        
        # Validate basic ruleset information
        required_info = ['name', 'description', 'features']
        for field in required_info:
            if field not in config:
                all_warnings.append(f"Missing '{field}' in ruleset information")
        
        return ValidationResult(len(all_errors) == 0, all_errors, all_warnings) 