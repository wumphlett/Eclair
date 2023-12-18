# Requirement Files Guide

## General
1. **Requirement files** hold the details of the team you're trying to optimize.
2. You can optimize up to **10 cookies** in each file.
3. Use `!reqdownload` to download a default file and view an example.

## Requirements
4. Requirements are specified under each cookie in a **yaml file**.
5. Each cookie can accept a collection of **validity requirements** and one **objective requirement**.

## Bot Moderator Permissions and Capabilities

### Actions on Behalf of Others
1. **Uploading Requirements for Users**: Moderators can upload requirement files directly into other users' inventories.
2. **Optimizing Using User's Topping Inventory**: Moderators have the capability to optimize configurations using the topping inventory of other users.

### Copying Requirement Files
1. **Copying Files**: Moderators can copy requirement files from their own personal files to different users.

### Code Implementation
- Checks for `moderator_only` ensure these actions are performed securely and appropriately within the bot's framework.

## Validity
Validity requirements specify the conditions that must be met for a cookie to be considered valid:
- **Simple**: Compare a substat to a benchmark. 
  - Example: `Cooldown >= 6.3`
- **Relative**: Compare a substat above or below a target.
  - Example: `ATK SPD below Rye`
  - Note: Targets must be other cookies listed in the file.
- **Range**: Specify a range of valid substat values.
  - Example: `28 <= Cooldown <= 28.5`
- **Equality**: Pin a substat to a specific value.
  - Example: `Cooldown == 28.3`

## Objective
Objective requirements define a goal to achieve with the cookie's stats:
- **Objective**: Specify a goal with a substat.
- **Special**: Include special requirements with relevant information.
  - `E[DMG]`: Calculated ideal balance between ATK and CRIT% to maximize the expected damage.
  - `Vitality`: Calculated ideal balance between DMG Resistance and HP to minimize damage taken.
  - `Combo`: Combines multiple substats.

## Modifiers
Modifiers allow the inclusion of additional factors that affect the final statistics of cookies:
- **Format**: Modifiers are defined in a separate section under `modifiers`.
- **Types**: Various stat modifiers can be included such as CRIT%, CRIT DMG, ATK MULT, etc.
- **Specification**: Each modifier should specify its source and value.

## Discord Commands
*Note that only a mod will need to use the optional `[user]` argument. Normal users will default these commands to be performed on themselves.*
- **Upload a file**: `!req upload`
  - Attach your .yaml file to the Discord message.
  - Use `!req upload [user]`
- **View files**: `!req view`
  - Displays all of your uploaded requirement files.
- **Copy a file**: `!req copy [user]`
  - Copies one of your requirement files to another user.
- **Download a file**: `!req download`
  - Downloads a requirement file.
- **Delete a file**: `!req delete`
  - Deletes a specified requirement file.

## Default Files
- **Upload default**: `!req def upload`
- **Download default**: `!req def download`
- **Delete default**: `!req def delete`


## Example
*Requirements in this example have a cookie's base ATK% buff, calculable with `!basestat <before> <after> [diff]`*
- See `!help basestat` for more information.
```yaml
example1.yaml
cookies:
- name: Werewolf
  requirements:
  - Cooldown >= 9
  - DMG Resist >= 10
  - ATK SPD >= 7.5
  - max: CRIT%
- name: Rye
  requirements:
  - max: E[DMG]
    ATK: 33.72
- name: Squid
  requirements:
  - ATK SPD below Werewolf
  - Cooldown >= 9
  - Cooldown <= 12
  - max: E[DMG]
    ATK: 29.52
- name: Cream Puff
  requirements:
  - Cooldown >= 7.5
  - CRIT% >= 55.7
  - max: E[DMG]
    CRIT%: 14.7
    ATK: 34.77
- name: Macaron
  requirements:
  - Cooldown >= 25
  - max: Combo
    substats:
    - Cooldown
    - DMG Resist
modifiers:
  CRIT%:
  - source: Double Macaron Buff
    value: 23
  CRIT DMG:
  - source: Moonstone Relic
    value: 18.2
  - source: Cream Puff MC
    value: 25
  ATK MULT:
  - source: The Order's Sacred Fork Treasure
    value: 0.3
```