load('ChibiMAP.mat')

figure
image(I);axis equal
hold on
for i=1:128
plot(X(i),Y(i),'ro');
end
hold off