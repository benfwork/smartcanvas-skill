# SmartCanvas Functions Reference

Captured from the SmartCanvas Variables function editor on June 30, 2026. Documentation text is copied from the function editor; examples are practical sample expressions using the displayed function names.

## Function List

- [Replace (input, replace, newValue)](#replace-input-replace-newvalue)
- [Remove](#remove)
- [HMACSHA256 Password](#hmacsha256-password)
- [HMACSHA256](#hmacsha256)
- [Last Part](#last-part)
- [First Part](#first-part)
- [Trim Right Side](#trim-right-side)
- [Trim Left Side](#trim-left-side)
- [Trim To Length](#trim-to-length)
- [Right](#right)
- [Left](#left)
- [Substr](#substr)
- [SHA256](#sha256)
- [SHA1](#sha1)
- [Reverse DNS Lookup](#reverse-dns-lookup)
- [Replace Curly Brackets](#replace-curly-brackets)
- [MD5](#md5)
- [Upper Case](#upper-case)
- [Lower Case](#lower-case)
- [Capitalize](#capitalize)
- [Url Encode](#url-encode)
- [Url Decode](#url-decode)
- [Html Encode](#html-encode)
- [Html Decode](#html-decode)
- [Create Password](#create-password)
- [Date Format (date, format, culture)](#date-format-date-format-culture)
- [Date Format (date, format)](#date-format-date-format)
- [Date Format (currentDateUTC, format)](#date-format-currentdateutc-format)
- [Date Format (currentDate, format)](#date-format-currentdate-format)
- [ParseInt](#parseint)
- [Add](#add)
- [Subtract](#subtract)
- [Divide (whole number)](#divide-whole-number)
- [Multiply (whole number)](#multiply-whole-number)
- [Multiply (floating point)](#multiply-floating-point)
- [Divide (floating point)](#divide-floating-point)
- [Random (min, max)](#random-min-max)
- [Age](#age)
- [Month Part](#month-part)
- [Year Part](#year-part)
- [Length](#length)
- [Current Date UTC](#current-date-utc)
- [Current Date](#current-date)
- [Add Days To Date](#add-days-to-date)
- [Add Hours To Date](#add-hours-to-date)
- [Add Minutes To Date](#add-minutes-to-date)
- [Has birthday today](#has-birthday-today)
- [Has birthday today (birthdayDate, dateFormat)](#has-birthday-today-birthdaydate-dateformat)
- [Is date in next month? (date, dateFormat)](#is-date-in-next-month-date-dateformat)
- [Has Birthday On Date](#has-birthday-on-date)
- [Is date in month N? (date, dateFormat, monthsToAdd)](#is-date-in-month-n-date-dateformat-monthstoadd)
- [Create calendar days text](#create-calendar-days-text)
- [Return month name](#return-month-name)

## Functions

### Replace (input, replace, newValue)

Replaces every occurence specified by the specified value.

- Function: `replace`
- Returns: `string`
- Example: `replace("blue shirt", "blue", "white")`

| Parameter | Type | Documentation |
| --- | --- | --- |
| Input | string | The input string. |
| replace | string | The value you want to replace. |
| newValue | string | The new value for the replacement. |

<details>
<summary>Copied SmartCanvas documentation</summary>

```text
Replaces every occurence specified by the specified value.
Returns: string
Parameters:
Name: Input
Description: The input string.
Type: string
Name: replace
Description: The value you want to replace.
Type: string
Name: newValue
Description: The new value for the replacement.
Type: string
replace
(
Input
	
,
replace
	
,
newValue
	
)
```

</details>

### Remove

Removes any of the mentioned chars in the input string

- Function: `removechars`
- Returns: `string`
- Example: `removechars("ABC-123", "-")`

| Parameter | Type | Documentation |
| --- | --- | --- |
| Input | string | The input string. |
| CharsToRemove | string | All characters that will be removed |

<details>
<summary>Copied SmartCanvas documentation</summary>

```text
Removes any of the mentioned chars in the input string
Returns: string
Parameters:
Name: Input
Description: The input string.
Type: string
Name: CharsToRemove
Description: All characters that will be removed
Type: string
removechars
(
Input
	
,
CharsToRemove
	
)
```

</details>

### HMACSHA256 Password

Returns a hmac sha256 suitable for login with hashed password.

- Function: `hmacsha256password`
- Returns: `string`
- Example: `hmacsha256password("user@example.com", "secret-salt")`

| Parameter | Type | Documentation |
| --- | --- | --- |
| Input | string | The input to hash. |
| Salt | string | Salt for this hash. |

<details>
<summary>Copied SmartCanvas documentation</summary>

```text
Returns a hmac sha256 suitable for login with hashed password.
Returns: string
Parameters:
Name: Input
Description: The input to hash.
Type: string
Name: Salt
Description: Salt for this hash.
Type: string
hmacsha256password
(
Input
	
,
Salt
	
)
```

</details>

### HMACSHA256

Returns the HMAC SHA256 hash in hex format of the given input.

- Function: `hmacsha256`
- Returns: `string`
- Example: `hmacsha256("hello", "secret-salt")`

| Parameter | Type | Documentation |
| --- | --- | --- |
| Input | string | The input to hash. |
| Salt | string | Salt for this hash. |

<details>
<summary>Copied SmartCanvas documentation</summary>

```text
Returns the HMAC SHA256 hash in hex format of the given input.
Returns: string
Parameters:
Name: Input
Description: The input to hash.
Type: string
Name: Salt
Description: Salt for this hash.
Type: string
hmacsha256
(
Input
	
,
Salt
	
)
```

</details>

### Last Part

Returns the last occurrence of the string after splitting it with the specified split string.

- Function: `lastPart`
- Returns: `string`
- Example: `lastPart("folder/subfolder/file.pdf", "/")`

| Parameter | Type | Documentation |
| --- | --- | --- |
| Input | string | The input string. |
| Splitter | string | The string you want to use as splitter. |

<details>
<summary>Copied SmartCanvas documentation</summary>

```text
Returns the last occurrence of the string after splitting it with the specified split string.
Returns: string
Parameters:
Name: Input
Description: The input string.
Type: string
Name: Splitter
Description: The string you want to use as splitter.
Type: string
lastPart
(
Input
	
,
Splitter
	
)
```

</details>

### First Part

Returns the first occurrence of the string after splitting it with the specified split string.

- Function: `firstPart`
- Returns: `string`
- Example: `firstPart("Last, First", ",")`

| Parameter | Type | Documentation |
| --- | --- | --- |
| Input | string | The input string. |
| Splitter | string | The string you want to use as splitter. |

<details>
<summary>Copied SmartCanvas documentation</summary>

```text
Returns the first occurrence of the string after splitting it with the specified split string.
Returns: string
Parameters:
Name: Input
Description: The input string.
Type: string
Name: Splitter
Description: The string you want to use as splitter.
Type: string
firstPart
(
Input
	
,
Splitter
	
)
```

</details>

### Trim Right Side

Cuts the specified length from the right side of the string.

- Function: `trimRight`
- Returns: `string`
- Example: `trimRight("ABCDEFG", 3)`

| Parameter | Type | Documentation |
| --- | --- | --- |
| Input | string | The input you want to cut something from the right side. |
| Length | integer | The length you want to cut from the right side. |

<details>
<summary>Copied SmartCanvas documentation</summary>

```text
Cuts the specified length from the right side of the string.
Returns: string
Parameters:
Name: Input
Description: The input you want to cut something from the right side.
Type: string
Name: Length
Description: The length you want to cut from the right side.
Type: integer
trimRight
(
Input
	
,
Length
	
)
```

</details>

### Trim Left Side

Cuts the specified length from the left side of the string.

- Function: `trimLeft`
- Returns: `string`
- Example: `trimLeft("ABCDEFG", 2)`

| Parameter | Type | Documentation |
| --- | --- | --- |
| Input | string | The input you want to cut something from the left side. |
| Length | integer | The length to cut from the left side. |

<details>
<summary>Copied SmartCanvas documentation</summary>

```text
Cuts the specified length from the left side of the string.
Returns: string
Parameters:
Name: Input
Description: The input you want to cut something from the left side.
Type: string
Name: Length
Description: The length to cut from the left side.
Type: integer
trimLeft
(
Input
	
,
Length
	
)
```

</details>

### Trim To Length

Returns the text trimmed to the specified length. Minimum length is 6.

- Function: `trimToLength`
- Returns: `string`
- Example: `trimToLength("Long department name", 10)`

| Parameter | Type | Documentation |
| --- | --- | --- |
| Input | string | The input you want to trim. |
| Length | integer | The length of the final output. |

<details>
<summary>Copied SmartCanvas documentation</summary>

```text
Returns the text trimmed to the specified length. Minimum length is 6.
Returns: string
Parameters:
Name: Input
Description: The input you want to trim.
Type: string
Name: Length
Description: The length of the final output.
Type: integer
trimToLength
(
Input
	
,
Length
	
)
```

</details>

### Right

Returns the specified length from the right side of the string.

- Function: `right`
- Returns: `string`
- Example: `right("INV-2026-0042", 4)`

| Parameter | Type | Documentation |
| --- | --- | --- |
| Input | string | The input you want to get something from the right side. |
| Length | integer | The length of the final output. |

<details>
<summary>Copied SmartCanvas documentation</summary>

```text
Returns the specified length from the right side of the string.
Returns: string
Parameters:
Name: Input
Description: The input you want to get something from the right side.
Type: string
Name: Length
Description: The length of the final output.
Type: integer
right
(
Input
	
,
Length
	
)
```

</details>

### Left

Returns the specified length from the left side of the string.

- Function: `left`
- Returns: `string`
- Example: `left("INV-2026-0042", 3)`

| Parameter | Type | Documentation |
| --- | --- | --- |
| Input | string | The input you want to get something from the left side. |
| Length | integer | The length of the final output. |

<details>
<summary>Copied SmartCanvas documentation</summary>

```text
Returns the specified length from the left side of the string.
Returns: string
Parameters:
Name: Input
Description: The input you want to get something from the left side.
Type: string
Name: Length
Description: The length of the final output.
Type: integer
left
(
Input
	
,
Length
	
)
```

</details>

### Substr

Extract a substring from text.

- Function: `substr`
- Returns: `string`
- Example: `substr("SmartCanvas", 5, 6)`

| Parameter | Type | Documentation |
| --- | --- | --- |
| Input | string | The input you want to get something from to be extracted. |
| StartIndex | integer | The start position. First character is at index 0. |
| Length | integer | The number of characters to extract. |

<details>
<summary>Copied SmartCanvas documentation</summary>

```text
Extract a substring from text.
Returns: string
Parameters:
Name: Input
Description: The input you want to get something from to be extracted.
Type: string
Name: StartIndex
Description: The start position. First character is at index 0.
Type: integer
Name: Length
Description: The number of characters to extract.
Type: integer
substr
(
Input
	
,
StartIndex
	
,
Length
	
)
```

</details>

### SHA256

Returns the sha256 hash in hex format of the given input.

- Function: `sha256`
- Returns: `string`
- Example: `sha256("hello")`

| Parameter | Type | Documentation |
| --- | --- | --- |
| Input | string | The value you want to create the hash from. |

<details>
<summary>Copied SmartCanvas documentation</summary>

```text
Returns the sha256 hash in hex format of the given input.
Returns: string
Parameters:
Name: Input
Description: The value you want to create the hash from.
Type: string
sha256
(
Input
	
)
```

</details>

### SHA1

Returns the sha1 hash in hex format of the given input.

- Function: `sha1`
- Returns: `string`
- Example: `sha1("hello")`

| Parameter | Type | Documentation |
| --- | --- | --- |
| Value | string | The value you want to create the hash from. |

<details>
<summary>Copied SmartCanvas documentation</summary>

```text
Returns the sha1 hash in hex format of the given input.
Returns: string
Parameters:
Name: Value
Description: The value you want to create the hash from.
Type: string
sha1
(
Value
	
)
```

</details>

### Reverse DNS Lookup

Returns a hostname for a given ip address.

- Function: `reverseDNS`
- Returns: `string`
- Example: `reverseDNS("8.8.8.8")`

| Parameter | Type | Documentation |
| --- | --- | --- |
| IpAddress | string | The ip address you want to know the hostname of. |

<details>
<summary>Copied SmartCanvas documentation</summary>

```text
Returns a hostname for a given ip address.
Returns: string
Parameters:
Name: IpAddress
Description: The ip address you want to know the hostname of.
Type: string
reverseDNS
(
IpAddress
	
)
```

</details>

### Replace Curly Brackets

Replaces curly brackets to two square brackets.

- Function: `replaceCurlyBrackets`
- Returns: `string`
- Example: `replaceCurlyBrackets("{FirstName}")`

| Parameter | Type | Documentation |
| --- | --- | --- |
| Value | string | The value you want to replace curly brackets from. |

<details>
<summary>Copied SmartCanvas documentation</summary>

```text
Replaces curly brackets to two square brackets.
Returns: string
Parameters:
Name: Value
Description: The value you want to replace curly brackets from.
Type: string
replaceCurlyBrackets
(
Value
	
)
```

</details>

### MD5

Returns the md5 hash in hex format of the given input.

- Function: `md5`
- Returns: `string`
- Example: `md5("hello")`

| Parameter | Type | Documentation |
| --- | --- | --- |
| Input | string | The value you want to create the hash from. |

<details>
<summary>Copied SmartCanvas documentation</summary>

```text
Returns the md5 hash in hex format of the given input.
Returns: string
Parameters:
Name: Input
Description: The value you want to create the hash from.
Type: string
md5
(
Input
	
)
```

</details>

### Upper Case

Returns a given input in upper case.

- Function: `upperCase`
- Returns: `string`
- Example: `upperCase("byu print")`

| Parameter | Type | Documentation |
| --- | --- | --- |
| Value | string | The value you want to make upper case. |

<details>
<summary>Copied SmartCanvas documentation</summary>

```text
Returns a given input in upper case.
Returns: string
Parameters:
Name: Value
Description: The value you want to make upper case.
Type: string
upperCase
(
Value
	
)
```

</details>

### Lower Case

Returns a given input in lower case.

- Function: `lowerCase`
- Returns: `string`
- Example: `lowerCase("BYU PRINT")`

| Parameter | Type | Documentation |
| --- | --- | --- |
| Value | string | The value you want to make lower case. |

<details>
<summary>Copied SmartCanvas documentation</summary>

```text
Returns a given input in lower case.
Returns: string
Parameters:
Name: Value
Description: The value you want to make lower case.
Type: string
lowerCase
(
Value
	
)
```

</details>

### Capitalize

Returns a given input with the first character in upper case and all others in lower case.

- Function: `capitalize`
- Returns: `string`
- Example: `capitalize("bENJAMIN")`

| Parameter | Type | Documentation |
| --- | --- | --- |
| Value | string | The value you want to capitalize. |

<details>
<summary>Copied SmartCanvas documentation</summary>

```text
Returns a given input with the first character in upper case and all others in lower case.
Returns: string
Parameters:
Name: Value
Description: The value you want to capitalize.
Type: string
capitalize
(
Value
	
)
```

</details>

### Url Encode

Encodes the value via url encoding.

- Function: `urlEncode`
- Returns: `string`
- Example: `urlEncode("https://example.com/?q=hello world")`

| Parameter | Type | Documentation |
| --- | --- | --- |
| Value | string | The value you want to url encode. |

<details>
<summary>Copied SmartCanvas documentation</summary>

```text
Encodes the value via url encoding.
Returns: string
Parameters:
Name: Value
Description: The value you want to url encode.
Type: string
urlEncode
(
Value
	
)
```

</details>

### Url Decode

Decodes an Url encoded value.

- Function: `urlDecode`
- Returns: `string`
- Example: `urlDecode("hello%20world")`

| Parameter | Type | Documentation |
| --- | --- | --- |
| Value | string | The value you want to url decode. |

<details>
<summary>Copied SmartCanvas documentation</summary>

```text
Decodes an Url encoded value.
Returns: string
Parameters:
Name: Value
Description: The value you want to url decode.
Type: string
urlDecode
(
Value
	
)
```

</details>

### Html Encode

Encodes the value via html encoding.

- Function: `htmlEncode`
- Returns: `string`
- Example: `htmlEncode("<strong>Hi</strong>")`

| Parameter | Type | Documentation |
| --- | --- | --- |
| Value | string | The value you want to html encode. |

<details>
<summary>Copied SmartCanvas documentation</summary>

```text
Encodes the value via html encoding.
Returns: string
Parameters:
Name: Value
Description: The value you want to html encode.
Type: string
htmlEncode
(
Value
	
)
```

</details>

### Html Decode

Decodes an html encoded value.

- Function: `htmlDecode`
- Returns: `string`
- Example: `htmlDecode("&lt;strong&gt;Hi&lt;/strong&gt;")`

| Parameter | Type | Documentation |
| --- | --- | --- |
| Value | string | The value you want to html decode. |

<details>
<summary>Copied SmartCanvas documentation</summary>

```text
Decodes an html encoded value.
Returns: string
Parameters:
Name: Value
Description: The value you want to html decode.
Type: string
htmlDecode
(
Value
	
)
```

</details>

### Create Password

Returns a random password with specified length.

- Function: `password`
- Returns: `string`
- Example: `password(12)`

| Parameter | Type | Documentation |
| --- | --- | --- |
| Length | integer | The length of the password. |

<details>
<summary>Copied SmartCanvas documentation</summary>

```text
Returns a random password with specified length.
Returns: string
Parameters:
Name: Length
Description: The length of the password.
Type: integer
password
(
Length
	
)
```

</details>

### Date Format (date, format, culture)

Returns a given date with specified format and culture.

- Function: `dateFormat`
- Returns: `string`
- Example: `dateFormat("2026-06-30", "MMMM d, yyyy", "en-US")`

| Parameter | Type | Documentation |
| --- | --- | --- |
| Date | date | A date. |
| DateFormat | string | The format for the date. E.g. yyyy-MM-dd (2012-12-31) or MM/dd/yyyy (12/31/2012). |
| CultureName | string | The culture name you want to format the date with. Only usefull when you use formats which are culture depended. |

<details>
<summary>Copied SmartCanvas documentation</summary>

```text
Returns a given date with specified format and culture.
Returns: string
Parameters:
Name: Date
Description: A date.
Type: date
Name: DateFormat
Description: The format for the date. E.g. yyyy-MM-dd (2012-12-31) or MM/dd/yyyy (12/31/2012).
Type: string
Name: CultureName
Description: The culture name you want to format the date with. Only usefull when you use formats which are culture depended.
Type: string
dateFormat
(
Date
	
,
DateFormat
	
,
CultureName
	
)
```

</details>

### Date Format (date, format)

Returns a given date with specified format.

- Function: `dateFormat`
- Returns: `string`
- Example: `dateFormat("2026-06-30", "MM/dd/yyyy")`

| Parameter | Type | Documentation |
| --- | --- | --- |
| Date | date | A date. |
| DateFormat | string | The format for the date. E.g. yyyy-MM-dd (2012-12-31) or MM/dd/yyyy (12/31/2012). |

<details>
<summary>Copied SmartCanvas documentation</summary>

```text
Returns a given date with specified format.
Returns: string
Parameters:
Name: Date
Description: A date.
Type: date
Name: DateFormat
Description: The format for the date. E.g. yyyy-MM-dd (2012-12-31) or MM/dd/yyyy (12/31/2012).
Type: string
dateFormat
(
Date
	
,
DateFormat
	
)
```

</details>

### Date Format (currentDateUTC, format)

Returns the current date in utc time with specified format.

- Function: `dateUtc`
- Returns: `string`
- Example: `dateUtc("yyyy-MM-dd")`

| Parameter | Type | Documentation |
| --- | --- | --- |
| DateFormat | string | The format for the date. E.g. yyyy-MM-dd (2012-12-31) or MM/dd/yyyy (12/31/2012). |

<details>
<summary>Copied SmartCanvas documentation</summary>

```text
Returns the current date in utc time with specified format.
Returns: string
Parameters:
Name: DateFormat
Description: The format for the date. E.g. yyyy-MM-dd (2012-12-31) or MM/dd/yyyy (12/31/2012).
Type: string
dateUtc
(
DateFormat
	
)
```

</details>

### Date Format (currentDate, format)

Returns a date with specified format.

- Function: `date`
- Returns: `string`
- Example: `date("yyyy")`

| Parameter | Type | Documentation |
| --- | --- | --- |
| DateFormat | string | The format for the date. E.g. yyyy-MM-dd (2012-12-31) or MM/dd/yyyy (12/31/2012). |

<details>
<summary>Copied SmartCanvas documentation</summary>

```text
Returns a date with specified format.
Returns: string
Parameters:
Name: DateFormat
Description: The format for the date. E.g. yyyy-MM-dd (2012-12-31) or MM/dd/yyyy (12/31/2012).
Type: string
date
(
DateFormat
	
)
```

</details>

### ParseInt

The parseInt method parses a value as a string and returns the first integer.

- Function: `parseInt`
- Returns: `integer`
- Example: `parseInt("42px")`

| Parameter | Type | Documentation |
| --- | --- | --- |
| Input | string | The value to be parsed. |

<details>
<summary>Copied SmartCanvas documentation</summary>

```text
The parseInt method parses a value as a string and returns the first integer.
Returns: integer
Parameters:
Name: Input
Description: The value to be parsed.
Type: string
parseInt
(
Input
	
)
```

</details>

### Add

Adds two numbers.

- Function: `+I`
- Returns: `integer`
- Example: `+I(2026, 1)`

| Parameter | Type | Documentation |
| --- | --- | --- |
| Number1 | integer | The first number you want to add to the second. |
| Number2 | integer | The second number you want to add to the first. |

<details>
<summary>Copied SmartCanvas documentation</summary>

```text
Adds two numbers.
Returns: integer
Parameters:
Name: Number1
Description: The first number you want to add to the second.
Type: integer
Name: Number2
Description: The second number you want to add to the first.
Type: integer
+I
(
Number1
	
,
Number2
	
)
```

</details>

### Subtract

Subtracts two numbers.

- Function: `-I`
- Returns: `integer`
- Example: `-I(2026, 2004)`

| Parameter | Type | Documentation |
| --- | --- | --- |
| Number1 | integer | The number you want to subtract the other from. |
| Number2 | integer | The number you want to subtract. |

<details>
<summary>Copied SmartCanvas documentation</summary>

```text
Subtracts two numbers.
Returns: integer
Parameters:
Name: Number1
Description: The number you want to subtract the other from.
Type: integer
Name: Number2
Description: The number you want to subtract.
Type: integer
-I
(
Number1
	
,
Number2
	
)
```

</details>

### Divide (whole number)

Divides two numbers rounded to the next whole number.

- Function: `/I`
- Returns: `integer`
- Example: `/I(9, 2)`

| Parameter | Type | Documentation |
| --- | --- | --- |
| Number1 | integer | The numerator. |
| Number2 | integer | The denominator. |

<details>
<summary>Copied SmartCanvas documentation</summary>

```text
Divides two numbers rounded to the next whole number.
Returns: integer
Parameters:
Name: Number1
Description: The numerator.
Type: integer
Name: Number2
Description: The denominator.
Type: integer
/I
(
Number1
	
,
Number2
	
)
```

</details>

### Multiply (whole number)

Multiplies two whole numbers.

- Function: `*I`
- Returns: `integer`
- Example: `*I(6, 7)`

| Parameter | Type | Documentation |
| --- | --- | --- |
| Number1 | integer | The first number. |
| Number2 | integer | The second number. |

<details>
<summary>Copied SmartCanvas documentation</summary>

```text
Multiplies two whole numbers.
Returns: integer
Parameters:
Name: Number1
Description: The first number.
Type: integer
Name: Number2
Description: The second number.
Type: integer
*I
(
Number1
	
,
Number2
	
)
```

</details>

### Multiply (floating point)

Multiplies two numbers.

- Function: `*S`
- Returns: `string`
- Example: `*S("2.5", "4")`

| Parameter | Type | Documentation |
| --- | --- | --- |
| Number1 | string | The first number. |
| Number2 | string | The second number. |

<details>
<summary>Copied SmartCanvas documentation</summary>

```text
Multiplies two numbers.
Returns: string
Parameters:
Name: Number1
Description: The first number.
Type: string
Name: Number2
Description: The second number.
Type: string
*S
(
Number1
	
,
Number2
	
)
```

</details>

### Divide (floating point)

Divides two numbers.

- Function: `/S`
- Returns: `string`
- Example: `/S("10", "4")`

| Parameter | Type | Documentation |
| --- | --- | --- |
| Number1 | string | The first number. |
| Number2 | string | The second number. |

<details>
<summary>Copied SmartCanvas documentation</summary>

```text
Divides two numbers.
Returns: string
Parameters:
Name: Number1
Description: The first number.
Type: string
Name: Number2
Description: The second number.
Type: string
/S
(
Number1
	
,
Number2
	
)
```

</details>

### Random (min, max)

Returns a random number.

- Function: `random`
- Returns: `integer`
- Example: `random(1, 100)`

| Parameter | Type | Documentation |
| --- | --- | --- |
| Min | integer | The inclusive lower bound. |
| Max | integer | The inclusive upper bound (max {0:n0}). |

<details>
<summary>Copied SmartCanvas documentation</summary>

```text
Returns a random number.
Returns: integer
Parameters:
Name: Min
Description: The inclusive lower bound.
Type: integer
Name: Max
Description: The inclusive upper bound (max {0:n0}).
Type: integer
random
(
Min
	
,
Max
	
)
```

</details>

### Age

Returns the current age for a given date.

- Function: `age`
- Returns: `integer`
- Example: `age("2004-06-30")`

| Parameter | Type | Documentation |
| --- | --- | --- |
| Date | date | The date (birthday) you need to calculate the age from. |

<details>
<summary>Copied SmartCanvas documentation</summary>

```text
Returns the current age for a given date.
Returns: integer
Parameters:
Name: Date
Description: The date (birthday) you need to calculate the age from.
Type: date
age
(
Date
	
)
```

</details>

### Month Part

Gets the month of a given date.

- Function: `month`
- Returns: `integer`
- Example: `month("2026-06-30")`

| Parameter | Type | Documentation |
| --- | --- | --- |
| Date | date | The date you want to know the month of. |

<details>
<summary>Copied SmartCanvas documentation</summary>

```text
Gets the month of a given date.
Returns: integer
Parameters:
Name: Date
Description: The date you want to know the month of.
Type: date
month
(
Date
	
)
```

</details>

### Year Part

Gets the year of a given date.

- Function: `year`
- Returns: `integer`
- Example: `year("2026-06-30")`

| Parameter | Type | Documentation |
| --- | --- | --- |
| Date | date | The date you want to know the year of. |

<details>
<summary>Copied SmartCanvas documentation</summary>

```text
Gets the year of a given date.
Returns: integer
Parameters:
Name: Date
Description: The date you want to know the year of.
Type: date
year
(
Date
	
)
```

</details>

### Length

Provides the length of a string.

- Function: `length`
- Returns: `integer`
- Example: `length("SmartCanvas")`

| Parameter | Type | Documentation |
| --- | --- | --- |
| Input | string | The string you want to get the length of. |

<details>
<summary>Copied SmartCanvas documentation</summary>

```text
Provides the length of a string.
Returns: integer
Parameters:
Name: Input
Description: The string you want to get the length of.
Type: string
length
(
Input
	
)
```

</details>

### Current Date UTC

Returns the current date as utc.

- Function: `dateUtc`
- Returns: `date`
- Example: `dateUtc()`

<details>
<summary>Copied SmartCanvas documentation</summary>

```text
Returns the current date as utc.
Returns: date
Parameters:
dateUtc
(
)
```

</details>

### Current Date

Returns the current date.

- Function: `date`
- Returns: `date`
- Example: `date()`

<details>
<summary>Copied SmartCanvas documentation</summary>

```text
Returns the current date.
Returns: date
Parameters:
date
(
)
```

</details>

### Add Days To Date

Adds the given day count to the given date.

- Function: `dateAddDays`
- Returns: `date`
- Example: `dateAddDays(date(), 7)`

| Parameter | Type | Documentation |
| --- | --- | --- |
| Date | date | A Date. |
| Days | integer | The days to add. This value can be negative. |

<details>
<summary>Copied SmartCanvas documentation</summary>

```text
Adds the given day count to the given date.
Returns: date
Parameters:
Name: Date
Description: A Date.
Type: date
Name: Days
Description: The days to add. This value can be negative.
Type: integer
dateAddDays
(
Date
	
,
Days
	
)
```

</details>

### Add Hours To Date

Adds the given hour count to the given date.

- Function: `dateAddHours`
- Returns: `date`
- Example: `dateAddHours(date(), 2)`

| Parameter | Type | Documentation |
| --- | --- | --- |
| Date | date | A Date. |
| Hours | integer | The hours to add. This value can be negative. |

<details>
<summary>Copied SmartCanvas documentation</summary>

```text
Adds the given hour count to the given date.
Returns: date
Parameters:
Name: Date
Description: A Date.
Type: date
Name: Hours
Description: The hours to add. This value can be negative.
Type: integer
dateAddHours
(
Date
	
,
Hours
	
)
```

</details>

### Add Minutes To Date

Adds the given minute count to the given date.

- Function: `dateAddMinutes`
- Returns: `date`
- Example: `dateAddMinutes(date(), 30)`

| Parameter | Type | Documentation |
| --- | --- | --- |
| Date | date | A Date. |
| Minutes | integer | The minutes to add. This value can be negative. |

<details>
<summary>Copied SmartCanvas documentation</summary>

```text
Adds the given minute count to the given date.
Returns: date
Parameters:
Name: Date
Description: A Date.
Type: date
Name: Minutes
Description: The minutes to add. This value can be negative.
Type: integer
dateAddMinutes
(
Date
	
,
Minutes
	
)
```

</details>

### Has birthday today

Checks for birthday.

- Function: `hasBirthday`
- Returns: `boolean`
- Example: `hasBirthday("2004-06-30")`

| Parameter | Type | Documentation |
| --- | --- | --- |
| Birthday | date | The date of birthday. |

<details>
<summary>Copied SmartCanvas documentation</summary>

```text
Checks for birthday.
Returns: boolean
Parameters:
Name: Birthday
Description: The date of birthday.
Type: date
hasBirthday
(
Birthday
	
)
```

</details>

### Has birthday today (birthdayDate, dateFormat)

Checks for birthday.

- Function: `hasBirthday`
- Returns: `boolean`
- Example: `hasBirthday("06/30/2004", "MM/dd/yyyy")`

| Parameter | Type | Documentation |
| --- | --- | --- |
| Birthday | string | The date as string. |
| DateFormat | string | The format of the date. |

<details>
<summary>Copied SmartCanvas documentation</summary>

```text
Checks for birthday.
Returns: boolean
Parameters:
Name: Birthday
Description: The date as string.
Type: string
Name: DateFormat
Description: The format of the date.
Type: string
hasBirthday
(
Birthday
	
,
DateFormat
	
)
```

</details>

### Is date in next month? (date, dateFormat)

Checks for a date occurence in the next month.

- Function: `isDateInNextMonth`
- Returns: `boolean`
- Example: `isDateInNextMonth("07/15/2026", "MM/dd/yyyy")`

| Parameter | Type | Documentation |
| --- | --- | --- |
| Date | string | The date as string. |
| DateFormat | string | The date to check for birthday. |

<details>
<summary>Copied SmartCanvas documentation</summary>

```text
Checks for a date occurence in the next month.
Returns: boolean
Parameters:
Name: Date
Description: The date as string.
Type: string
Name: DateFormat
Description: The date to check for birthday.
Type: string
isDateInNextMonth
(
Date
	
,
DateFormat
	
)
```

</details>

### Has Birthday On Date

Checks for birthday on a specified date.

- Function: `hasBirthdayOnDay`
- Returns: `boolean`
- Example: `hasBirthdayOnDay("2004-06-30", "2026-06-30")`

| Parameter | Type | Documentation |
| --- | --- | --- |
| Birthday | date | The birthday. |
| Date | date | The date to check for birthday. |

<details>
<summary>Copied SmartCanvas documentation</summary>

```text
Checks for birthday on a specified date.
Returns: boolean
Parameters:
Name: Birthday
Description: The birthday.
Type: date
Name: Date
Description: The date to check for birthday.
Type: date
hasBirthdayOnDay
(
Birthday
	
,
Date
	
)
```

</details>

### Is date in month N? (date, dateFormat, monthsToAdd)

Checks for a date occurence in a specific month (only this month).

- Function: `isDateInMonthN`
- Returns: `boolean`
- Example: `isDateInMonthN("08/15/2026", "MM/dd/yyyy", 2)`

| Parameter | Type | Documentation |
| --- | --- | --- |
| Date | string | The date as string. |
| DateFormat | string | The format of the date. |
| Month Count | integer | The count of months to add. |

<details>
<summary>Copied SmartCanvas documentation</summary>

```text
Checks for a date occurence in a specific month (only this month).
Returns: boolean
Parameters:
Name: Date
Description: The date as string.
Type: string
Name: DateFormat
Description: The format of the date.
Type: string
Name: Month Count
Description: The count of months to add.
Type: integer
isDateInMonthN
(
Date
	
,
DateFormat
	
,
Month Count
	
)
```

</details>

### Create calendar days text

Creates calendar days as text lines for a specific month

- Function: `createCalendarDays`
- Returns: `string`
- Example: `createCalendarDays(2026, 6, 0, "numbers")`

| Parameter | Type | Documentation |
| --- | --- | --- |
| Year | number | The start year. |
| Month | number | The month for which the days are generated (1 = January) |
| Start Offset | number | Month counting start offset |
| Return format | string | Possible values are 'full', 'numbers', 'text' |

<details>
<summary>Copied SmartCanvas documentation</summary>

```text
Creates calendar days as text lines for a specific month
Returns: string
Parameters:
Name: Year
Description: The start year.
Type: number
Name: Month
Description: The month for which the days are generated (1 = January)
Type: number
Name: Start Offset
Description: Month counting start offset
Type: number
Name: Return format
Description: Possible values are 'full', 'numbers', 'text'
Type: string
createCalendarDays
(
Year
	
,
Month
	
,
Start Offset
	
,
Return format
	
)
```

</details>

### Return month name

Returns the name of a month by its index (starting at 1 = January)

- Function: `getMonthNameByMonthIndex`
- Returns: `string`
- Example: `getMonthNameByMonthIndex(6, 0)`

| Parameter | Type | Documentation |
| --- | --- | --- |
| Month index | number | The month index starts at 1 = January |
| Start Offset | number | Month counting start offset |

<details>
<summary>Copied SmartCanvas documentation</summary>

```text
Returns the name of a month by its index (starting at 1 = January)
Returns: string
Parameters:
Name: Month index
Description: The month index starts at 1 = January
Type: number
Name: Start Offset
Description: Month counting start offset
Type: number
getMonthNameByMonthIndex
(
Month index
	
,
Start Offset
	
)
```

</details>
