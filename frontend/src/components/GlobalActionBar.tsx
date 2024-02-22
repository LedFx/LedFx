/* eslint-disable prettier/prettier */
import { Button, IconButton, Slider, Stack, useTheme } from '@mui/material';
import type { SxProps, Theme } from '@mui/material';
import { Brightness7, PauseOutlined, PlayArrow } from '@mui/icons-material';
import { useEffect, useState } from 'react'
import useStore from '../store/useStore';

const GlobalActionBar = ({
  className,
  sx,
  height,
  type,
}: {
  className?: string | undefined;
  sx?: SxProps<Theme> | undefined;
  height?: number;
  type?: 'button' | 'icon' | 'indicator';
}) => {
  const theme = useTheme();

  const getSystemConfig = useStore((state) => state.getSystemConfig);
  const setSystemConfig = useStore((state) => state.setSystemConfig);
  const globalBrightness = useStore((state) => state.config.global_brightness);
  const setSystemSetting = (setting: string, value: any) => {
    setSystemConfig({ [setting]: value }).then(() => getSystemConfig());
  };

  const [brightness, setBrightness] = useState(globalBrightness * 100);
  const paused = useStore((state) => state.paused);
  const togglePause = useStore((state) => state.togglePause);

  useEffect(() => {
    setBrightness(globalBrightness * 100);
  }, [globalBrightness]);


  return (
    <Stack
      className={className}
      direction="row"
      sx={{ minWidth: 250, alignItems: 'center', marginRight: 2, ...sx }}
    >
      {type === 'icon' ? (
        <IconButton
          color="inherit"
          aria-label="play-pause"
          onClick={() => {
            togglePause();
          }}
          style={{
            margin: '0 8px 0 8px', color: '#fff'
          }}
        >
          {paused ? <PlayArrow sx={{ fontSize: 32 }} /> : <PauseOutlined sx={{ fontSize: 32 }} />}
        </IconButton>
      ) : type === 'button' ? (
        <Button
          variant="text"
          color="secondary"
          aria-label="play-pause"
          sx={{ borderRadius: 3 }}
          onClick={() => {
            togglePause();
          }}
          style={{
            margin: '0 16px 0 0', color: '#fff'
          }}
        >
          {paused ? <PlayArrow  sx={{ fontSize: 32 }} /> : <PauseOutlined  sx={{ fontSize: 32 }} />}
        </Button>
      ) : (
        // <BladeIcon name="Brightness7" />
        <Brightness7 sx={{ ml: 2, mr: 2 }} />
      )}
      <Slider
        sx={{
          height,
          display: 'flex',
          // color: 'inherit',
          p: 0,
          '& .MuiSlider-thumb': {
            height: 32,
            width: 32,
            color: '#dedede',
            backgroundSize: '60%',
            backgroundRepeat: 'no-repeat',
            backgroundPosition: 'center',
            backgroundImage:
              'url("data:image/svg+xml,%3Csvg xmlns=\'http://www.w3.org/2000/svg\' class=\'MuiSvgIcon-root MuiSvgIcon-fontSizeMedium MuiBox-root css-kaxv2e\' focusable=\'false\' aria-hidden=\'true\' viewBox=\'0 0 24 24\' data-testid=\'WbSunnySharpIcon\'%3E%3Cpath fill=\'%23666\' d=\'m6.76 4.84-1.8-1.79-1.41 1.41 1.79 1.79 1.42-1.41zM4 10.5H1v2h3v-2zm9-9.95h-2V3.5h2V.55zm7.45 3.91-1.41-1.41-1.79 1.79 1.41 1.41 1.79-1.79zm-3.21 13.7 1.79 1.8 1.41-1.41-1.8-1.79-1.4 1.4zM20 10.5v2h3v-2h-3zm-8-5c-3.31 0-6 2.69-6 6s2.69 6 6 6 6-2.69 6-6-2.69-6-6-6zm-1 16.95h2V19.5h-2v2.95zm-7.45-3.91 1.41 1.41 1.79-1.8-1.41-1.41-1.79 1.8z\'%3E%3C/path%3E%3C/svg%3E")',
            // 'url(/icon.png)',
            // opacity: 0,
            '& input:after': {
              // content: 'hi',
            },
          },
          '& .MuiSlider-track': {
            height: 3,
          },
          '& .MuiSlider-rail': {
            backgroundColor: '#666',
            height: 3,
          },
          '& .MuiSliderValueLabel ': {
            fontSize: 12,
            fontWeight: 'normal',
            top: -6,
            backgroundColor: 'unset',
            color: theme.palette.text.primary,
            '&:before': {
              display: 'none',
            },
            '& *': {
              background: 'transparent',
              color: theme.palette.mode === 'dark' ? '#fff' : '#000',
            },
          },
        }}
        // valueLabelDisplay="on"
        value={brightness}
        onChange={(_e, val) => typeof val === 'number' && setBrightness(val)}
        step={1}
        min={0}
        max={100}
        onChangeCommitted={(_e, val) =>
          typeof val === 'number' && setSystemSetting('global_brightness', val / 100)
        }
      />
    </Stack>
  );
};

GlobalActionBar.defaultProps = {
  className: undefined,
  sx: undefined,
  height: 15,
  type: 'icon',
};

export default GlobalActionBar;
