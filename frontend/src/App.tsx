import React from 'react';
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import { Layout, Menu } from 'antd';
import { UploadOutlined, VideoCameraOutlined, FileTextOutlined, TagOutlined } from '@ant-design/icons';
import TaskList from './components/TaskList';
import VideoDetail from './components/VideoDetail';
import CorpusList from './components/CorpusList';
import AnnotationList from './components/AnnotationList';

const { Header, Content, Sider } = Layout;

const menuItems = [
  { key: '/', icon: <UploadOutlined />, label: '任务管理' },
  { key: '/videos', icon: <VideoCameraOutlined />, label: '视频列表' },
  { key: '/corpus', icon: <FileTextOutlined />, label: '语料库' },
  { key: '/annotations', icon: <TagOutlined />, label: '标注管理' },
];

function App() {
  const [collapsed, setCollapsed] = React.useState(false);

  return (
    <Router>
      <Layout style={{ minHeight: '100vh' }}>
        <Sider collapsible collapsed={collapsed} onCollapse={setCollapsed}>
          <div className="logo" style={{ fontSize: '18px', textAlign: 'center', padding: '16px', color: '#fff' }}>
            {collapsed ? '语料工具' : '多模态语料工具'}
          </div>
          <Menu theme="dark" defaultSelectedKeys={['/']} mode="inline" items={menuItems} />
        </Sider>
        <Layout>
          <Header style={{ padding: 0 }} />
          <Content style={{ margin: '24px 16px', padding: 24, minHeight: 280 }}>
            <Routes>
              <Route path="/" element={<TaskList />} />
              <Route path="/videos" element={<TaskList />} />
              <Route path="/videos/:id" element={<VideoDetail />} />
              <Route path="/corpus" element={<CorpusList />} />
              <Route path="/annotations" element={<AnnotationList />} />
            </Routes>
          </Content>
        </Layout>
      </Layout>
    </Router>
  );
}

export default App;
