/* eslint-disable prettier/prettier */
import { useTheme, Stack } from '@mui/material';
import BladeFrame from '../../components/SchemaForm/components/BladeFrame';
import DbRow from './DbRow';
import useStore from '../../store/useStore';

const DbStats = () => {
  const theme = useTheme();
  const config = useStore((state) => state.config);
  const devices = useStore((state) => state.devices);
  const virtuals = useStore((state) => state.virtuals);
  const scenes = useStore((state) => state.scenes);
  const devicesOnline = Object.keys(devices).filter((d) => devices[d].online);
  const virtualsReal = Object.keys(virtuals).filter(
    (d) => !virtuals[d].is_device
  );

  const pixelTotalOnline = Object.keys(devices)
    .map((d) => devices[d].online && devices[d].config.pixel_count)
    .reduce((a, b) => a + b, 0);

  const pixelTotal = Object.keys(devices)
    .map((d) => devices[d].config.pixel_count)
    .reduce((a, b) => a + b, 0);
  return (
    <BladeFrame
      labelStyle={{
        background: theme.palette.background.default,
        color: theme.palette.primary.main,
      }}
      style={{
        borderColor: theme.palette.primary.main,
        padding: 20,
        minWidth: 280,
      }}
      title="Stats"
    >
      <Stack width="100%">
        <DbRow left="Pixels:" right={`${pixelTotalOnline} / ${pixelTotal}`} />
        <DbRow
          left="Devices:"
          right={`${Object.keys(devicesOnline).length} / ${
            Object.keys(devices).length
          }`}
        />
        <DbRow left="Virtuals:" right={String(virtualsReal.length)} />
        <DbRow left="Scenes:" right={String(Object.keys(scenes).length)} />
        <DbRow
          left="User Colors:"
          right={String(Object.keys(config.user_colors).length +
            Object.keys(config.user_gradients).length)}
        />
        <DbRow
          left="User Presets:"
          right={String(Object.values(config.user_presets).length
            ? Object.values(config.user_presets)
              .map((e: any) => Object.keys(e).length)
              .reduce((a: number, b: number) => a + b, 0)
            : 0)}
        />
      </Stack>
    </BladeFrame>
  );
};

export default DbStats;
