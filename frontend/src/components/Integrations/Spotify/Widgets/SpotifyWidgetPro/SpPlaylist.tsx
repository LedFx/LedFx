/* eslint-disable prettier/prettier */
/* eslint-disable @typescript-eslint/indent */
import * as React from 'react';
import {
  DataGrid,
  GridColDef,
  GridValueGetterParams,
  GridRowParams,
} from '@mui/x-data-grid';

import { Card, Grid, IconButton , Stack, useTheme } from '@mui/material';
import { PlayCircleFilled } from '@mui/icons-material';
import useStore from '../../../../../store/useStore';
import { spotifyPlaySong } from '../../../../../utils/spotifyProxies';
import { classes } from './SpTriggerTable';
import { SpStateContext, SpotifyStateContext } from '../../SpotifyProvider';

// function isScrolledIntoView(el: any) {
//   const rect = el.getBoundingClientRect();
//   const elemTop = rect.top;
//   const elemBottom = rect.bottom;

//   // Only completely visible elements return true:
//   const isVisible = elemTop >= 0 && elemBottom <= rect.innerHeight;
//   // Partially visible elements return true:
//   // isVisible = elemTop < window.innerHeight && elemBottom >= 0;
//   return isVisible;
// }

export default function SpPlaylist() {
  const theme = useTheme()
  const playlist = useStore((state) => state.spotify.playlist);
  const playerState = React.useContext(SpotifyStateContext);
  const spCtx = React.useContext(SpStateContext);
  const playlistUri = playerState?.context?.metadata?.uri;
  const spotifyDevice = useStore((state) => state.spotify.spotifyDevice);
  const premium = !!playerState?.track_window?.current_track?.album?.name
  const columns: GridColDef[] = [
    {
      field: 'id',
      headerName: 'ID',
      width: 60,
      align: 'center',
      headerAlign: 'center'
    },
    {
      field: 'actions',
      headerName: ' ',
      width: 50,
      headerAlign: 'center',
      align: 'center',
      sortable: false,
      filterable: false,
      disableColumnMenu: true,
      renderCell: (params: any) => (
        <Stack direction="row" alignItems="center" spacing={0}>
          <IconButton
            aria-label="playstart"
            color="inherit"
            onClick={() => {
              spotifyPlaySong(
                spotifyDevice,
                params.row.track.id,
                undefined,
                playlistUri
              );
            }}
          >
            <PlayCircleFilled fontSize="inherit" />
          </IconButton>
        </Stack>
      ),
    },
    {
      field: 'songName',
      headerName: 'Song name',
      width: 500,
      sortable: false,
      filterable: false,
      disableColumnMenu: true,
      valueGetter: (params: GridValueGetterParams) =>
        `${params?.row?.track?.artists?.[0]?.name || ''} - ${
          params?.row?.track?.name || ''
        }`,
    },
  ];
  const rows = playlist.map((item: any, index: number) => ({
    ...item,
    id: index,
  })) || [{ id: 1 }];

  React.useEffect(() => {
    const playing = document.querySelector(
      '.MuiDataGrid-root.playlist .MuiDataGrid-row.currently_playing'
    );
    if (playing) {
      playing.scrollIntoView();
    }
  }, [playerState?.track_window?.current_track?.name]);
  // console.log(playerState?.context.metadata?.current_item, rows.map((r: any)=>r.track))
  return (
    <Grid xl={premium ? 7 : 12} lg={premium ? 5 : 12} md={12} xs={12} item>
      <Card sx={{ height: 250 }}>
        <DataGrid
          className={`${classes.root} playlist`}
          rows={rows}
          columns={columns}
          disableRowSelectionOnClick
          // headerHeight={0}
          hideFooter
          disableVirtualization
          // showColumnRightBorder={false}
          columnVisibilityModel={{
            id: !premium,
            actions: premium,
          }}
          onRowDoubleClick={(params: any) => {
            spotifyPlaySong(
              spotifyDevice,
              params.row.track.id,
              undefined,
              playlistUri
            );
          }}
          sx={{
            boxShadow: 2,
            color: '#fff',
            border: 1,
            borderColor: '#666',
            '& .MuiDataGrid-columnHeaders': {
              borderBottom: 0,
            },

            '& .currently_playing': {
              backgroundColor: `${theme.palette.primary.main}20`,
              color: theme.palette.text.primary
            },
          }}
          // pageSize={rows.length}
          // rowsPerPageOptions={[rows.length]}
          getRowClassName={(params: GridRowParams<any>) =>{
            return ((params.row.track?.name ===
            playerState?.context.metadata?.current_item?.name) && (
              params.row.track.artists?.[0].uri ===
              playerState?.context.metadata?.current_item.artists?.[0].uri
            ) || (params.row.track?.name ===
              spCtx?.item?.name && params.row.track.artists?.[0]?.name === spCtx?.item?.artists?.[0]?.name) )
              ? 'currently_playing'
              : ''}
          }
        />
      </Card>
    </Grid>
  );
}
