use std::ffi::OsStr;
use unicode_general_category::{GeneralCategory, get_general_category};

use crate::{
    cli::{AnnotationRequest, AnnotationSeverity},
    error::ShoutxError,
    input::VALUE_LIMIT,
};

use super::normalize::strip_final;

const MESSAGE_UTF16_LIMIT: usize = 4_096;

#[derive(Clone, Copy)]
enum PropertyKind {
    Text,
    Number,
}

struct Property<'a> {
    name: &'static [u8],
    value: &'a [u8],
    kind: PropertyKind,
}

fn bytes(value: &OsStr) -> Result<&[u8], ShoutxError> {
    value
        .to_str()
        .map(str::as_bytes)
        .ok_or_else(|| ShoutxError::failure("annotation option is not valid UTF-8"))
}

fn text_property(value: &OsStr) -> Result<&[u8], ShoutxError> {
    let value = bytes(value)?;
    if value.len() > VALUE_LIMIT {
        return Err(ShoutxError::failure(
            "annotation property exceeds size limit",
        ));
    }
    if value.contains(&0) {
        return Err(ShoutxError::failure("annotation property contains NUL"));
    }
    let text = std::str::from_utf8(value)
        .map_err(|_| ShoutxError::failure("annotation option is not valid UTF-8"))?;
    if text.is_empty() {
        return Err(ShoutxError::failure("annotation property is empty"));
    }
    if value.first() == Some(&b'=') {
        return Err(ShoutxError::failure(
            "annotation property begins with equals",
        ));
    }
    if text.chars().next_back().is_some_and(|character| {
        character != '\r' && character != '\n' && character.is_whitespace()
    }) {
        return Err(ShoutxError::failure(
            "annotation property ends with whitespace",
        ));
    }
    Ok(value)
}

fn number(value: &OsStr) -> Result<i32, ShoutxError> {
    let value = bytes(value)?;
    if value.is_empty() || !value.iter().all(u8::is_ascii_digit) {
        return Err(ShoutxError::failure(
            "annotation position is not an unsigned decimal integer",
        ));
    }
    let significant = value
        .iter()
        .position(|digit| *digit != b'0')
        .map_or(&value[value.len()..], |index| &value[index..]);
    if significant.is_empty() {
        return Err(ShoutxError::failure("annotation position is out of range"));
    }
    if significant.len() > 10 {
        return Err(ShoutxError::failure("annotation position is out of range"));
    }
    let mut result = 0i32;
    for digit in significant {
        result = result
            .checked_mul(10)
            .and_then(|current| current.checked_add(i32::from(digit - b'0')))
            .ok_or_else(|| ShoutxError::failure("annotation position is out of range"))?;
    }
    Ok(result)
}

fn encoded_len(value: &[u8], property: bool) -> Option<usize> {
    value.iter().try_fold(0usize, |length, byte| {
        length.checked_add(
            if matches!(byte, b'%' | b'\r' | b'\n') || (property && matches!(byte, b':' | b',')) {
                3
            } else {
                1
            },
        )
    })
}

fn push_encoded(output: &mut Vec<u8>, value: &[u8], property: bool) {
    for byte in value {
        match byte {
            b'%' => output.extend_from_slice(b"%25"),
            b'\r' => output.extend_from_slice(b"%0D"),
            b'\n' => output.extend_from_slice(b"%0A"),
            b':' if property => output.extend_from_slice(b"%3A"),
            b',' if property => output.extend_from_slice(b"%2C"),
            _ => output.push(*byte),
        }
    }
}

pub fn encode(request: AnnotationRequest, mut message: Vec<u8>) -> Result<Vec<u8>, ShoutxError> {
    if message.len() > VALUE_LIMIT {
        return Err(ShoutxError::failure("value exceeds size limit"));
    }
    std::str::from_utf8(&message).map_err(|_| ShoutxError::failure("value is not valid UTF-8"))?;
    if message.contains(&0) {
        return Err(ShoutxError::failure("value contains NUL"));
    }
    strip_final(&mut message);
    let message_text = std::str::from_utf8(&message)
        .map_err(|_| ShoutxError::failure("value is not valid UTF-8"))?;
    if message_text.is_empty() || message_text.chars().all(char::is_whitespace) {
        return Err(ShoutxError::failure(
            "annotation message is empty or whitespace only",
        ));
    }
    if message_text.chars().next().is_some_and(|character| {
        matches!(
            get_general_category(character),
            GeneralCategory::NonspacingMark
                | GeneralCategory::SpacingMark
                | GeneralCategory::EnclosingMark
        )
    }) {
        return Err(ShoutxError::failure(
            "annotation message begins with a Unicode mark",
        ));
    }
    if message_text.encode_utf16().count() > MESSAGE_UTF16_LIMIT {
        return Err(ShoutxError::failure(
            "annotation message exceeds semantic size limit",
        ));
    }

    let title = request.title.as_deref().map(text_property).transpose()?;
    let file = request.file.as_deref().map(text_property).transpose()?;
    let line = request.line.as_deref().map(number).transpose()?;
    let end_line = request.end_line.as_deref().map(number).transpose()?;
    let column = request.column.as_deref().map(number).transpose()?;
    let end_column = request.end_column.as_deref().map(number).transpose()?;

    if end_line.is_some() && line.is_none() {
        return Err(ShoutxError::failure("end line requires line"));
    }
    if (column.is_some() || end_column.is_some()) && line.is_none() {
        return Err(ShoutxError::failure("column requires line"));
    }
    if end_column.is_some() && column.is_none() {
        return Err(ShoutxError::failure("end column requires column"));
    }
    if end_line.zip(line).is_some_and(|(end, start)| end < start) {
        return Err(ShoutxError::failure("end line precedes line"));
    }
    if end_column
        .zip(column)
        .is_some_and(|(end, start)| end < start)
    {
        return Err(ShoutxError::failure("end column precedes column"));
    }
    if column.is_some() && end_line.zip(line).is_some_and(|(end, start)| end != start) {
        return Err(ShoutxError::failure("columns require a single-line range"));
    }

    let line_text = line.map(|value| value.to_string());
    let end_line_text = end_line.map(|value| value.to_string());
    let column_text = column.map(|value| value.to_string());
    let end_column_text = end_column.map(|value| value.to_string());
    let properties = [
        title.map(|value| Property {
            name: b"title",
            value,
            kind: PropertyKind::Text,
        }),
        file.map(|value| Property {
            name: b"file",
            value,
            kind: PropertyKind::Text,
        }),
        line_text.as_deref().map(|value| Property {
            name: b"line",
            value: value.as_bytes(),
            kind: PropertyKind::Number,
        }),
        end_line_text.as_deref().map(|value| Property {
            name: b"endLine",
            value: value.as_bytes(),
            kind: PropertyKind::Number,
        }),
        column_text.as_deref().map(|value| Property {
            name: b"col",
            value: value.as_bytes(),
            kind: PropertyKind::Number,
        }),
        end_column_text.as_deref().map(|value| Property {
            name: b"endColumn",
            value: value.as_bytes(),
            kind: PropertyKind::Number,
        }),
    ];
    let present = properties.iter().flatten().count();
    let severity = match request.severity {
        AnnotationSeverity::Notice => b"notice".as_slice(),
        AnnotationSeverity::Warning => b"warning".as_slice(),
        AnnotationSeverity::Error => b"error".as_slice(),
    };
    let mut capacity = 2usize
        .checked_add(severity.len())
        .and_then(|value| value.checked_add(if present == 0 { 2 } else { 3 }))
        .and_then(|value| encoded_len(&message, false)?.checked_add(value))
        .and_then(|value| value.checked_add(1))
        .ok_or_else(|| ShoutxError::failure("encoded annotation exceeds size limit"))?;
    for property in properties.iter().flatten() {
        capacity = capacity
            .checked_add(property.name.len() + 1)
            .and_then(|value| {
                value.checked_add(encoded_len(
                    property.value,
                    matches!(property.kind, PropertyKind::Text),
                )?)
            })
            .and_then(|value| value.checked_add(1))
            .ok_or_else(|| ShoutxError::failure("encoded annotation exceeds size limit"))?;
    }

    let mut output = Vec::with_capacity(capacity);
    output.extend_from_slice(b"::");
    output.extend_from_slice(severity);
    if present != 0 {
        output.push(b' ');
        let mut first = true;
        for property in properties.iter().flatten() {
            if !first {
                output.push(b',');
            }
            first = false;
            output.extend_from_slice(property.name);
            output.push(b'=');
            push_encoded(
                &mut output,
                property.value,
                matches!(property.kind, PropertyKind::Text),
            );
        }
    }
    output.extend_from_slice(b"::");
    push_encoded(&mut output, &message, false);
    output.push(b'\n');
    Ok(output)
}
