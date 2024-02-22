import { useEffect } from 'react'
import Box from '@mui/material/Box'
import {
  DataGrid,
  GridColDef,
  GridEventListener,
  GridRenderCellParams
} from '@mui/x-data-grid'
import { Card, CardMedia, Typography, useTheme } from '@mui/material'
import BladeIcon from '../../components/Icons/BladeIcon/BladeIcon'
import useStore from '../../store/useStore'

export default function ScenesMostUsed({
  scenes,
  activateScene,
  title,
  db
}: any) {
  const theme = useTheme()
  const count = useStore((state) => state.count)
  // const [mostUsedScenes, setMostUsedScenes] = useState({});
  const mostUsedScenes = useStore((state) => state.mostUsedScenes)
  const setMostUsedScenes = useStore((state) => state.setMostUsedScenes)

  const handleEvent: GridEventListener<'rowClick'> = (params) =>
    activateScene(
      Object.keys(scenes).find((s: any) => scenes[s].name === params.row?.name)
    )

  useEffect(() => {
    Object.keys(count).map((key: string) => setMostUsedScenes(key, count[key]))
  }, [scenes, count])

  const sceneImage = (iconName: string, table?: boolean) =>
    iconName && iconName.startsWith('image:') ? (
      <CardMedia
        image={iconName.split('image:')[1]}
        title="Contemplative Reptile"
        sx={{ width: '100%', height: '100%' }}
      />
    ) : (
      <BladeIcon scene={!table} name={iconName} />
    )
  const columns: GridColDef[] = [
    { field: 'id', headerName: 'ID', width: 70 },
    {
      field: 'scene_image',
      headerName: 'Image',
      width: db ? 100 : 150,
      renderCell: (params: GridRenderCellParams) =>
        sceneImage(params.value || 'Wallpaper', true)
    },
    {
      field: 'name',
      headerName: 'Name',
      width: db ? 136 : 220
    },
    {
      field: 'used',
      headerName: 'Used',
      type: 'number',
      width: 20
    }
  ]

  return (
    <Card
      sx={{
        background: db ? 'transparent' : '',
        borderColor: db ? 'transparent' : ''
      }}
    >
      <Box
        sx={{
          height: db ? 301 : 293,
          width: '100%',
          maxWidth: '470px',
          m: '0 auto'
        }}
      >
        {!db && (
          <Typography
            color="GrayText"
            variant="h6"
            sx={{
              pl: 1,
              pt: 0.5,
              pb: 0.5,
              border: '1px solid',
              borderColor: db ? 'transparent' : theme.palette.divider,
              borderBottom: 0
            }}
          >
            {title}
          </Typography>
        )}
        <DataGrid
          onRowClick={handleEvent}
          rowHeight={50}
          columns={db ? columns.filter((c) => c.field !== 'used') : columns}
          hideFooter
          // headerHeight={1}
          pageSizeOptions={[5]}
          disableRowSelectionOnClick
          rows={Object.values(mostUsedScenes).map((v: any, i: number) => ({
            id: i + 1,
            ...v
          }))}
          initialState={{
            // pagination: {
            //   pageSize: 100,
            // },
            sorting: {
              sortModel: [{ field: 'used', sort: 'desc' }]
            },
            columns: {
              columnVisibilityModel: {
                id: false,
                scene_tags: false
              }
            }
          }}
          sx={{
            borderColor: db ? 'transparent' : theme.palette.divider,
            '&.MuiDataGrid-root .MuiDataGrid-cell:focus-within': {
              outline: 'none !important'
            }
          }}
        />
      </Box>
    </Card>
  )
}
