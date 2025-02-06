export const Modal = ({ children, onClose }: { children: React.ReactNode; onClose: () => void }) => (
    <div className="fixed inset-0 flex items-center justify-center bg-black bg-opacity-50">
        <div className="bg-white p-4 rounded-lg">
            {children}
            <button className="mt-4 px-4 py-2 bg-gray-500 text-white rounded" onClick={onClose}>Close</button>
        </div>
    </div>
);
