# Custom configuration for tmux-powerline
# Based on config.sh.default with modifications

# General settings
export TMUX_POWERLINE_DEBUG_MODE_ENABLED="false"
export TMUX_POWERLINE_PATCHED_FONT_IN_USE="true"
export TMUX_POWERLINE_THEME="default"

# Weather configuration - Changed to Fahrenheit
export TMUX_POWERLINE_SEG_WEATHER_DATA_PROVIDER="yrno"
export TMUX_POWERLINE_SEG_WEATHER_UNIT="f"  # f for Fahrenheit (was c for Celsius)
export TMUX_POWERLINE_SEG_WEATHER_UPDATE_PERIOD="600"
export TMUX_POWERLINE_SEG_WEATHER_LOCATION_UPDATE_PERIOD="86400"
export TMUX_POWERLINE_SEG_WEATHER_LAT="auto"
export TMUX_POWERLINE_SEG_WEATHER_LON="auto"

# Time configuration - 24-hour format
export TMUX_POWERLINE_SEG_TIME_FORMAT="%H:%M"  # %H:%M for 24-hour, %I:%M %p for 12-hour

# Custom segments - override the theme defaults
# Left side: removed hostname, lan_ip, and wan_ip
TMUX_POWERLINE_LEFT_STATUS_SEGMENTS=(
	"tmux_session_info 148 234"
	"vcs_branch 29 88"
)

# Right side: removed load (CPU load)
TMUX_POWERLINE_RIGHT_STATUS_SEGMENTS=(
	"pwd 89 211"
	"battery 137 127"
	"weather 37 255"
	"date_day 235 136"
	"date 235 136 ${TMUX_POWERLINE_SEPARATOR_LEFT_THIN}"
	"time 235 136 ${TMUX_POWERLINE_SEPARATOR_LEFT_THIN}"
)
