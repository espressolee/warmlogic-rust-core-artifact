"""Tests for Schema Validator."""

from __future__ import annotations

import pytest

from warm_logic_core.os.schema_validator import (
    FieldType,
    FieldSchema,
    ObjectSchema,
    SchemaValidator,
    ValidationResult,
    ValidationError,
    validate_os_state,
    validate_scheduler_status,
)


class TestFieldSchema:
    """Tests for FieldSchema."""

    def test_basic_field(self):
        """Test basic field schema."""
        schema = FieldSchema("name", FieldType.STRING)

        assert schema.name == "name"
        assert schema.field_type == FieldType.STRING
        assert schema.required is False

    def test_required_field(self):
        """Test required field."""
        schema = FieldSchema("id", FieldType.STRING, required=True)

        assert schema.required is True

    def test_numeric_bounds(self):
        """Test numeric bounds."""
        schema = FieldSchema(
            "score",
            FieldType.FLOAT,
            min_value=0.0,
            max_value=1.0,
        )

        assert schema.min_value == 0.0
        assert schema.max_value == 1.0


class TestSchemaValidator:
    """Tests for SchemaValidator."""

    def test_valid_object(self):
        """Test validating a valid object."""
        schema = ObjectSchema(
            "test",
            properties={
                "name": FieldSchema("name", FieldType.STRING, required=True),
                "value": FieldSchema("value", FieldType.INTEGER),
            },
        )
        validator = SchemaValidator(schema)

        data = {"name": "test", "value": 42}
        result = validator.validate(data)

        assert result.valid is True
        assert len(result.errors) == 0

    def test_missing_required_field(self):
        """Test missing required field."""
        schema = ObjectSchema(
            "test",
            properties={
                "name": FieldSchema("name", FieldType.STRING, required=True),
            },
        )
        validator = SchemaValidator(schema)

        data = {}
        result = validator.validate(data)

        assert result.valid is False
        assert len(result.errors) == 1
        assert "missing" in result.errors[0].message.lower()

    def test_invalid_type(self):
        """Test invalid field type."""
        schema = ObjectSchema(
            "test",
            properties={
                "value": FieldSchema("value", FieldType.INTEGER),
            },
        )
        validator = SchemaValidator(schema)

        data = {"value": "not an integer"}
        result = validator.validate(data)

        assert result.valid is False
        assert "type" in result.errors[0].message.lower()

    def test_null_not_allowed(self):
        """Test null when not allowed."""
        schema = ObjectSchema(
            "test",
            properties={
                "name": FieldSchema(
                    "name", FieldType.STRING, nullable=False, required=True
                ),
            },
        )
        validator = SchemaValidator(schema)

        data = {"name": None}
        result = validator.validate(data)

        assert result.valid is False
        assert "null" in result.errors[0].message.lower()

    def test_null_allowed(self):
        """Test null when allowed."""
        schema = ObjectSchema(
            "test",
            properties={
                "name": FieldSchema("name", FieldType.STRING, nullable=True),
            },
        )
        validator = SchemaValidator(schema)

        data = {"name": None}
        result = validator.validate(data)

        assert result.valid is True

    def test_enum_values(self):
        """Test enum value validation."""
        schema = ObjectSchema(
            "test",
            properties={
                "status": FieldSchema(
                    "status",
                    FieldType.STRING,
                    enum_values=["active", "inactive"],
                ),
            },
        )
        validator = SchemaValidator(schema)

        valid_data = {"status": "active"}
        invalid_data = {"status": "unknown"}

        assert validator.validate(valid_data).valid is True
        assert validator.validate(invalid_data).valid is False

    def test_min_value(self):
        """Test minimum value."""
        schema = ObjectSchema(
            "test",
            properties={
                "score": FieldSchema("score", FieldType.FLOAT, min_value=0.0),
            },
        )
        validator = SchemaValidator(schema)

        valid_data = {"score": 0.5}
        invalid_data = {"score": -1.0}

        assert validator.validate(valid_data).valid is True
        assert validator.validate(invalid_data).valid is False

    def test_max_value(self):
        """Test maximum value."""
        schema = ObjectSchema(
            "test",
            properties={
                "score": FieldSchema("score", FieldType.FLOAT, max_value=1.0),
            },
        )
        validator = SchemaValidator(schema)

        valid_data = {"score": 0.5}
        invalid_data = {"score": 2.0}

        assert validator.validate(valid_data).valid is True
        assert validator.validate(invalid_data).valid is False

    def test_min_length(self):
        """Test minimum length."""
        schema = ObjectSchema(
            "test",
            properties={
                "name": FieldSchema("name", FieldType.STRING, min_length=3),
            },
        )
        validator = SchemaValidator(schema)

        valid_data = {"name": "abc"}
        invalid_data = {"name": "ab"}

        assert validator.validate(valid_data).valid is True
        assert validator.validate(invalid_data).valid is False

    def test_max_length(self):
        """Test maximum length."""
        schema = ObjectSchema(
            "test",
            properties={
                "name": FieldSchema("name", FieldType.STRING, max_length=5),
            },
        )
        validator = SchemaValidator(schema)

        valid_data = {"name": "abc"}
        invalid_data = {"name": "abcdefg"}

        assert validator.validate(valid_data).valid is True
        assert validator.validate(invalid_data).valid is False

    def test_pattern(self):
        """Test pattern matching."""
        schema = ObjectSchema(
            "test",
            properties={
                "code": FieldSchema(
                    "code", FieldType.STRING, pattern=r"^[A-Z]{3}-\d{3}$"
                ),
            },
        )
        validator = SchemaValidator(schema)

        valid_data = {"code": "ABC-123"}
        invalid_data = {"code": "invalid"}

        assert validator.validate(valid_data).valid is True
        assert validator.validate(invalid_data).valid is False

    def test_array_items(self):
        """Test array item validation."""
        schema = ObjectSchema(
            "test",
            properties={
                "scores": FieldSchema(
                    "scores",
                    FieldType.ARRAY,
                    item_schema=FieldSchema("item", FieldType.INTEGER),
                ),
            },
        )
        validator = SchemaValidator(schema)

        valid_data = {"scores": [1, 2, 3]}
        invalid_data = {"scores": [1, "two", 3]}

        assert validator.validate(valid_data).valid is True
        assert validator.validate(invalid_data).valid is False

    def test_nested_object(self):
        """Test nested object validation."""
        schema = ObjectSchema(
            "test",
            properties={
                "config": FieldSchema(
                    "config",
                    FieldType.OBJECT,
                    properties={
                        "enabled": FieldSchema("enabled", FieldType.BOOLEAN),
                    },
                ),
            },
        )
        validator = SchemaValidator(schema)

        valid_data = {"config": {"enabled": True}}
        invalid_data = {"config": {"enabled": "yes"}}

        assert validator.validate(valid_data).valid is True
        assert validator.validate(invalid_data).valid is False

    def test_custom_validator(self):
        """Test custom validator function."""

        def validate_even(value):
            if value % 2 != 0:
                return "Value must be even"
            return None

        schema = ObjectSchema(
            "test",
            properties={
                "num": FieldSchema(
                    "num",
                    FieldType.INTEGER,
                    custom_validator=validate_even,
                ),
            },
        )
        validator = SchemaValidator(schema)

        valid_data = {"num": 4}
        invalid_data = {"num": 3}

        assert validator.validate(valid_data).valid is True
        assert validator.validate(invalid_data).valid is False

    def test_strict_mode(self):
        """Test strict mode for unknown fields."""
        schema = ObjectSchema(
            "test",
            properties={
                "name": FieldSchema("name", FieldType.STRING),
            },
        )
        validator = SchemaValidator(schema, strict=True)

        data = {"name": "test", "unknown": "field"}
        result = validator.validate(data)

        assert result.valid is True  # Unknown fields are warnings
        assert len(result.warnings) == 1

    def test_root_not_object(self):
        """Test validation fails if root is not object."""
        schema = ObjectSchema("test", properties={})
        validator = SchemaValidator(schema)

        result = validator.validate("not an object")

        assert result.valid is False
        assert "Root must be an object" in result.errors[0].message


class TestValidationResult:
    """Tests for ValidationResult."""

    def test_result_to_dict(self):
        """Test result serialization."""
        result = ValidationResult(
            valid=False,
            errors=[ValidationError("field", "error message")],
        )

        data = result.to_dict()

        assert data["valid"] is False
        assert data["error_count"] == 1


class TestPredefinedSchemas:
    """Tests for predefined schemas."""

    def test_validate_os_state(self):
        """Test OS state validation."""
        valid_data = {
            "metrics": {"health": 0.9},
            "last_updated": 1234567890.0,
        }

        result = validate_os_state(valid_data)

        assert result.valid is True

    def test_validate_os_state_missing_metrics(self):
        """Test OS state validation with missing metrics."""
        invalid_data = {"last_updated": 1234567890.0}

        result = validate_os_state(invalid_data)

        assert result.valid is False

    def test_validate_scheduler_status(self):
        """Test scheduler status validation."""
        valid_data = {
            "timestamp": "2024-01-01T00:00:00Z",
            "risk_score": 0.5,
        }

        result = validate_scheduler_status(valid_data)

        assert result.valid is True

    def test_validate_scheduler_status_invalid_risk(self):
        """Test scheduler status with invalid risk score."""
        invalid_data = {
            "timestamp": "2024-01-01T00:00:00Z",
            "risk_score": 1.5,  # Above max
        }

        result = validate_scheduler_status(invalid_data)

        assert result.valid is False
