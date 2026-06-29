import React, { useState, useEffect } from 'react';
import { useParams } from 'react-router-dom';
import { Descriptions, Spin, Button, message } from 'antd';
import axios from 'axios';

interface Video {
  id: string;
  url: string;
  platform: string;
  title: string | null;
  duration: number | null;
  resolution: string | null;
  status: string;
  file_path: string | null;
  created_at: string;
  updated_at: string;
}

function VideoDetail() {
  const { id } = useParams<{ id: string }>();
  const [video, setVideo] = useState<Video | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchVideo();
  }, [id]);

  const fetchVideo = async () => {
    if (!id) return;
    try {
      const response = await axios.get(`/api/v1/videos/${id}`);
      setVideo(response.data);
    } catch (error) {
      message.error('获取视频详情失败');
    } finally {
      setLoading(false);
    }
  };

  const fetchCorpus = async () => {
    if (!id) return;
    try {
      const response = await axios.get(`/api/v1/corpus/${id}`);
      console.log('Corpus:', response.data);
      message.success('语料数据获取成功');
    } catch (error) {
      message.error('获取语料失败');
    }
  };

  if (loading) {
    return <Spin tip="加载中..." />;
  }

  if (!video) {
    return <div>视频不存在</div>;
  }

  return (
    <div>
      <h2>视频详情</h2>
      <Descriptions bordered column={2} style={{ marginBottom: 16 }}>
        <Descriptions.Item label="ID">{video.id}</Descriptions.Item>
        <Descriptions.Item label="标题">{video.title || '-'}</Descriptions.Item>
        <Descriptions.Item label="链接" span={2}>
          <a href={video.url} target="_blank" rel="noopener noreferrer">
            {video.url}
          </a>
        </Descriptions.Item>
        <Descriptions.Item label="平台">{video.platform}</Descriptions.Item>
        <Descriptions.Item label="分辨率">{video.resolution || '-'}</Descriptions.Item>
        <Descriptions.Item label="时长">
          {video.duration ? `${video.duration}秒` : '-'}
        </Descriptions.Item>
        <Descriptions.Item label="状态">{video.status}</Descriptions.Item>
        <Descriptions.Item label="文件路径">{video.file_path || '-'}</Descriptions.Item>
        <Descriptions.Item label="创建时间">{video.created_at}</Descriptions.Item>
        <Descriptions.Item label="更新时间">{video.updated_at}</Descriptions.Item>
      </Descriptions>
      <Button type="primary" onClick={fetchCorpus}>
        获取语料数据
      </Button>
    </div>
  );
}

export default VideoDetail;
