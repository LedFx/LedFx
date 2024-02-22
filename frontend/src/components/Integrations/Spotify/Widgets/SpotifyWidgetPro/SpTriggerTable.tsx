import {
  DataGrid,
  GridColDef,
  GridRowParams,
  GridCellParams
} from '@mui/x-data-grid'
import { styled } from '@mui/material/styles'
import {
  DeleteForever,
  NotStarted,
  PlayCircleFilled
} from '@mui/icons-material'
import { useContext, useEffect } from 'react'
import {
  Card,
  FormControl,
  IconButton,
  Stack,
  Select,
  SelectChangeEvent,
  MenuItem
} from '@mui/material'
import useStore from '../../../../../store/useStore'
import { spotifyPlaySong } from '../../../../../utils/spotifyProxies'
import Popover from '../../../../Popover/Popover'
import { SpStateContext, SpotifyStateContext } from '../../SpotifyProvider'
import { getTime } from '../../../../../utils/helpers'

const PREFIX = 'SpTriggerTable'

export const classes = {
  root: `${PREFIX}-root`,
  select: `${PREFIX}-select`
}

const Root = styled('div')(({ theme }: any) => ({
  [`& .${classes.select}`]: {
    color: '#fff !important'
  },
  '& .currently_playing, .currently_playing, .currently_playing.MuiDataGrid-row, .currently_playing.MuiDataGrid-row:hover, .currently_playing.MuiDataGrid-row.Mui-hovered':
    {
      backgroundColor: `${theme.palette.primary.main}20`,
      color: theme.palette.text.primary
    },
  [`& .${classes.root}`]: {
    '&.MuiDataGrid-root .MuiDataGrid-footerContainer .MuiTablePagination-root':
      {
        color: theme.palette.text.secondary
      },
    '&.MuiDataGrid-root .MuiButtonBase-root.MuiIconButton-root': {
      color: theme.palette.text.secondary
    },
    '&.MuiDataGrid-root .MuiDataGrid-cell': {
      borderColor: '#333'
    },
    '&.MuiDataGrid-root .MuiDataGrid-cell:focus, &.MuiDataGrid-root .MuiDataGrid-cell:focus-within':
      {
        outline: 'none'
      },

    '& .currently_playing, .currently_playing, .currently_playing.MuiDataGrid-row, .currently_playing.MuiDataGrid-row:hover, .currently_playing.MuiDataGrid-row.Mui-hovered':
      {
        backgroundColor: `${theme.palette.primary.main}20`,
        color: theme.palette.text.primary
      },
    '& .activated, .activated.MuiDataGrid-row:hover, .activated.MuiDataGrid-row.Mui-hovered':
      {
        backgroundColor: `${theme.palette.primary.main}50`,
        color: theme.palette.text.primary
      },
    '& .disabled.MuiDataGrid-row': {
      pointerEvents: 'none',
      color: '#666'
    },
    '& .disabled.MuiDataGrid-row .MuiIconButton-root': {
      pointerEvents: 'none',
      color: '#666'
    }
  }
}))

export default function SpotifyTriggerTable() {
  const integrations = useStore((state) => state.integrations)
  const scenes = useStore((state) => state.scenes)
  const getIntegrations = useStore((state) => state.getIntegrations)
  const spotifyDevice = useStore((state) => state.spotify.spotifyDevice)
  const playerState = useContext(SpotifyStateContext)
  const spCtx = useContext(SpStateContext)
  const spTriggersList = useStore((state) => state.spotify.spTriggersList)
  const deleteSpTrigger = useStore((state) => state.deleteSpTrigger)
  const getSpTriggers = useStore((state) => state.getSpTriggers)
  const addToSpTriggerList = useStore((state) => state.addToSpTriggerList)
  const getScenes = useStore((state) => state.getScenes)
  const editSpotifySongTrigger = useStore((state) => state.editSpSongTrigger)
  const premium = !!playerState?.track_window?.current_track?.album?.name

  useEffect(() => {
    getSpTriggers()
    getScenes()
  }, [])

  // Here we get the current triggers from list and set to global state
  useEffect(() => {
    const triggersNew: any = []
    let id = 1
    if (integrations?.spotify?.data) {
      const temp = integrations?.spotify?.data
      Object.keys(temp).map((key) => {
        const temp1 = temp[key]
        const sceneName = temp1?.name
        const sceneId = temp1?.name
        Object.keys(temp1).map((key1) => {
          if (temp1[key1]?.constructor === Array) {
            triggersNew.push({
              id,
              trigger_id: `${temp1[key1][0]}-${temp1[key1][2]}`,
              songId: temp1[key1][0],
              songName: temp1[key1][1],
              position: getTime(temp1[key1][2]),
              position_ms: temp1[key1][2],
              sceneId,
              sceneName
            })
            id += 1
          }

          return true
        })
        return true
      })
      addToSpTriggerList(triggersNew, 'create')
    }
  }, [integrations])

  const updateSpTrigger = (rowData: any, val: any) => {
    let sceneKey
    if (scenes) {
      Object.keys(scenes)?.map((key: any) => {
        if (scenes[key]?.name === val) {
          sceneKey = key
        }
        return null
      })
    }
    addToSpTriggerList({ ...rowData, sceneId: val }, 'update')
    const data = {
      scene_id: sceneKey,
      song_id: rowData?.songId,
      song_name: rowData?.songName,
      song_position: rowData?.position_ms
    }
    editSpotifySongTrigger(data).then(() => getIntegrations())
  }
  const deleteTriggerHandler = (paramsTemp: any) => {
    deleteSpTrigger({
      data: {
        trigger_id: paramsTemp?.row?.trigger_id
      }
    }).then(() => getIntegrations())
  }
  const columns: GridColDef[] = [
    {
      field: 'id',
      headerName: 'ID',
      width: 60,
      align: 'center',
      headerAlign: 'center'
    },
    {
      field: 'songName',
      headerName: 'Song',
      width: 400
    },
    {
      field: 'position',
      headerName: 'Position',
      width: 90,
      headerAlign: 'center',
      align: 'center'
    },

    {
      field: 'sceneId',
      headerName: 'Scene',
      width: 120,
      headerAlign: 'center',
      align: 'center',
      renderCell: (params: any) => {
        return (
          <FormControl fullWidth>
            <Select
              style={{
                color: 'white'
              }}
              classes={{
                icon: classes.select
              }}
              labelId="scene-select-label"
              value={params?.row?.sceneId}
              label="Scene"
              onChange={(e: SelectChangeEvent) => {
                updateSpTrigger(params?.row, e.target.value)
              }}
            >
              {/* <MenuItem value="sceneId" /> */}
              {Object.keys(scenes).map((s: any, i: number) => (
                <MenuItem key={i} value={scenes[s]?.name || s}>
                  {scenes[s]?.name || s}
                </MenuItem>
              ))}
            </Select>
          </FormControl>
        )
      }
    },
    {
      field: 'actions',
      headerName: 'Actions',
      width: 180,
      headerAlign: 'center',
      align: 'center',
      renderCell: (params: any) => (
        <Stack direction="row" alignItems="center" spacing={0}>
          <Popover
            variant="text"
            color="inherit"
            icon={<DeleteForever />}
            style={{ minWidth: 40 }}
            onConfirm={() => {
              deleteTriggerHandler(params)
            }}
          />
          {premium && (
            <>
              <IconButton
                aria-label="play"
                color="inherit"
                onClick={() => {
                  spotifyPlaySong(
                    spotifyDevice,
                    params.row.songId,
                    params.row.position_ms
                  )
                }}
              >
                <PlayCircleFilled fontSize="inherit" />
              </IconButton>
              <IconButton
                aria-label="playstart"
                color="inherit"
                onClick={() => {
                  spotifyPlaySong(spotifyDevice, params.row.songId)
                }}
              >
                <NotStarted fontSize="inherit" />
              </IconButton>
            </>
          )}
        </Stack>
      )
    }
  ]

  const rows = spTriggersList || [{ id: 1 }]
  return (
    <Root
      style={{
        display: 'flex',
        width: '100%'
      }}
    >
      <Card sx={{ display: 'flex', width: '100%' }}>
        <DataGrid
          className={classes.root}
          autoHeight
          // checkboxSelection
          disableRowSelectionOnClick
          onRowDoubleClick={(params: any) => {
            if (premium) spotifyPlaySong(spotifyDevice, params.row.songId)
          }}
          sx={{
            boxShadow: 2,
            color: '#fff',
            border: 1,
            borderColor: '#666',
            '& .sceneStyle': {
              border: '1px solid',
              borderColor: '#fff !important',
              padding: '0px'
            }
          }}
          columns={columns}
          rows={rows}
          getRowClassName={(params: GridRowParams<any>) =>
            params.row.songId ===
            (
              playerState?.context.metadata?.current_item || spCtx?.item
            )?.uri.split(':')[2]
              ? (playerState?.position || spCtx?.progress_ms || 0) >
                params.row.position_ms
                ? 'activated'
                : 'currently_playing'
              : ''
          }
          getCellClassName={(params: GridCellParams<any>) => {
            if (params?.field === 'sceneId') {
              return 'sceneStyle'
            }
            return ''
          }}
        />
      </Card>
    </Root>
  )
}
