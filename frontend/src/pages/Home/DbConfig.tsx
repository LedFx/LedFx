/* eslint-disable prettier/prettier */
import { useTheme, Stack } from '@mui/material';
import BladeFrame from '../../components/SchemaForm/components/BladeFrame';
import DbRow from './DbRow';
import useStore from '../../store/useStore';

const DbConfig = () => {
  const theme = useTheme();
  const config = useStore((state) => state.config);


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
        // marginBottom: '5rem',
      }}
      title="Core Config"
    >
      <Stack width="100%">
        <DbRow left='Host:' right={config.host} />
        <DbRow left='Port:' right={config.port} />
        {config.port_s && (
          <DbRow left='Port (SSL):' right={config.port_s} />
        )}
      </Stack>
    </BladeFrame>
  );
};

export default DbConfig;
